"""Compatibility sidecar translating LiteLLM decisions requests to Gemini Decisions API.

Run via ``uvicorn gemini_decision_adapter:app`` on port 8080 (see
``Dockerfile.adapter`` and ``docker-compose.yml``). LiteLLM's ``complexity_router``
(configured in ``config.yaml`` under ``anthropic-ladder`` and ``gemini-ladder``)
uses ``gemini-decision-1`` as an ``oss_classifier``, which LiteLLM dispatches via
its ``hosted_vllm`` / SystemOne decisions protocol because upstream LiteLLM does
not yet natively support Google's Gemini Decisions API (``v1beta/decisions``).

Pointing ``gemini-decision-1`` at ``http://gemini-decision-adapter:8080`` with
``model: hosted_vllm/gemini-decision-1`` allows LiteLLM to send its standard
decisions payload while this service handles the protocol translation:

1. **Request translation**: Strips the ``hosted_vllm/`` routing prefix from
   ``model``, maps ``state`` and optional ``images`` into Gemini's ``input``
   string or multimodal block list, and normalizes ``questions`` criteria schemas
   (``choice``, ``score``, ``noul``).
2. **Authentication**: Injects ``GEMINI_API_KEY`` via the ``x-goog-api-key``
   header so ``config.yaml`` can keep ``api_key: dummy`` for the local sidecar.
3. **Response translation**: Extracts ``answers`` and normalizes Gemini's
   ``total_input_tokens`` / ``total_output_tokens`` usage fields into
   ``input_tokens`` / ``output_tokens`` expected by LiteLLM.
4. **Endpoint aliases**: Exposes ``/v1/systemone``, ``/v1/decisions``, and
   ``/decisions`` to match the paths LiteLLM's decisions client may append to
   ``api_base``, plus ``/health`` for Docker Compose readiness checks.
"""

import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Any

import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO").upper())
logger = logging.getLogger("gemini_decision_adapter")

GEMINI_DECISIONS_URL = "https://generativelanguage.googleapis.com/v1beta/decisions"
DEFAULT_MODEL = "gemini-decision-1"


# ---------------------------------------------------------------------------
# Payload translation helpers (LiteLLM/SystemOne <-> Gemini Decisions API)
# ---------------------------------------------------------------------------


def _translate_image(image: Any) -> dict[str, Any] | None:
    """Convert a SystemOne/LiteLLM image entry into a Gemini ``input`` image block.

    Supports ``{"content_type", "base64"}`` dicts, ``data:<mime>;base64,...``
    URIs, and ``http(s)://`` URLs. Returns ``None`` for unrecognized entries so
    callers can safely skip them.
    """
    if isinstance(image, dict):
        content_type = image.get("content_type")
        data = image.get("base64")
        if content_type and data:
            return {"type": "image", "mime_type": content_type, "data": data}
        return None
    if isinstance(image, str):
        if image.startswith("data:") and ";base64," in image:
            header, data = image.split(";base64,", 1)
            mime_type = header[len("data:") :].split(";", 1)[0].strip().lower()
            return {"type": "image", "mime_type": mime_type, "data": data}
        if image.startswith(("http://", "https://")):
            return {"type": "image", "uri": image}
    return None


def _translate_input(body: dict[str, Any]) -> str | list[dict[str, Any]]:
    """Map SystemOne ``state`` and optional ``images`` to Gemini ``input``.

    Gemini accepts a plain string when only text is present, or a list of typed
    content blocks when images are attached.
    """
    state = body.get("state", "")
    state_text = state if isinstance(state, str) else json.dumps(state)
    images = body.get("images")
    if not images:
        return state_text

    blocks: list[dict[str, Any]] = []
    if state_text:
        blocks.append({"type": "text", "text": state_text})
    for image in images:
        block = _translate_image(image)
        if block is not None:
            blocks.append(block)
    # Fall back to plain text if all image entries were invalid or skipped.
    return blocks or state_text


def _translate_questions(questions: dict[str, Any]) -> dict[str, Any]:
    """Normalize LiteLLM/SystemOne ``questions`` into Gemini Decisions format.

    Ensures ``instructions`` and ``criteria`` values conform to Gemini's strict
    string/container expectations for each question ``type`` (``choice``,
    ``score``, and ``noul``).
    """
    translated: dict[str, Any] = {}
    for key, raw_question in questions.items():
        if not isinstance(raw_question, dict):
            continue
        q_type = raw_question.get("type")
        instructions = raw_question.get("instructions")
        if instructions is not None and not isinstance(instructions, str):
            instructions = json.dumps(instructions)

        question: dict[str, Any] = {"type": q_type}
        if instructions is not None:
            question["instructions"] = instructions

        criteria = raw_question.get("criteria")
        if q_type == "choice" and isinstance(criteria, dict):
            # Gemini choice criteria map option keys to string descriptions.
            question["criteria"] = {
                str(opt_key): "" if opt_val is None else (opt_val if isinstance(opt_val, str) else json.dumps(opt_val))
                for opt_key, opt_val in criteria.items()
            }
        elif q_type == "score" and isinstance(criteria, list):
            # Gemini score criteria expect a list of string rubric items.
            question["criteria"] = [
                item if isinstance(item, str) else json.dumps(item) for item in criteria
            ]
        elif q_type == "noul" and isinstance(criteria, dict):
            # Drop null criteria entries so Gemini does not reject optional fields.
            cleaned = {
                str(k): (v if isinstance(v, str) else json.dumps(v))
                for k, v in criteria.items()
                if v is not None
            }
            if cleaned:
                question["criteria"] = cleaned

        translated[key] = question
    return translated


def _translate_response(gemini_payload: dict[str, Any], model: str) -> dict[str, Any]:
    """Convert a Gemini Decisions response into the format LiteLLM expects.

    Preserves ``answers`` and normalizes Gemini's ``total_input_tokens`` /
    ``total_output_tokens`` counters to ``input_tokens`` / ``output_tokens`` for
    LiteLLM spend and usage tracking.
    """
    response: dict[str, Any] = {
        "model": gemini_payload.get("model") or model,
        "answers": gemini_payload.get("answers", {}),
    }
    usage = gemini_payload.get("usage")
    if isinstance(usage, dict):
        response["usage"] = {
            "input_tokens": int(usage.get("total_input_tokens", usage.get("input_tokens", 0)) or 0),
            "output_tokens": int(usage.get("total_output_tokens", usage.get("output_tokens", 0)) or 0),
        }
    return response


# ---------------------------------------------------------------------------
# ASGI lifecycle and HTTP handlers
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: Starlette):
    """Manage a shared ``httpx.AsyncClient`` for connection pooling across requests."""
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
        app.state.http = client
        yield


async def health(request: Request) -> JSONResponse:
    """Return ``200 OK`` for Docker Compose container readiness checks."""
    return JSONResponse({"status": "ok"})


async def decisions(request: Request) -> Response:
    """Translate an incoming LiteLLM decisions request and forward it to Gemini."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return JSONResponse({"error": {"message": "GEMINI_API_KEY is not configured"}}, status_code=500)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": {"message": "Invalid JSON body"}}, status_code=400)

    if not isinstance(body, dict):
        return JSONResponse({"error": {"message": "Request body must be a JSON object"}}, status_code=400)

    # LiteLLM configures the deployment as ``hosted_vllm/gemini-decision-1`` so it
    # routes to this adapter; strip the provider prefix before calling Gemini.
    raw_model = str(body.get("model") or DEFAULT_MODEL)
    model = raw_model.removeprefix("hosted_vllm/") or DEFAULT_MODEL

    gemini_request = {
        "model": model,
        "input": _translate_input(body),
        "questions": _translate_questions(body.get("questions") or {}),
    }

    client: httpx.AsyncClient = request.app.state.http
    try:
        upstream = await client.post(
            GEMINI_DECISIONS_URL,
            headers={
                "x-goog-api-key": api_key,
                "Content-Type": "application/json",
            },
            json=gemini_request,
        )
    except httpx.HTTPError as exc:
        logger.exception("Upstream request to Gemini Decisions API failed")
        return JSONResponse({"error": {"message": f"Upstream request failed: {exc}"}}, status_code=502)

    # Pass upstream 4xx/5xx responses through verbatim so LiteLLM logs the exact Gemini error.
    if upstream.status_code >= 400:
        logger.warning("Gemini Decisions API returned %s: %s", upstream.status_code, upstream.text)
        return Response(
            content=upstream.content,
            status_code=upstream.status_code,
            media_type=upstream.headers.get("content-type", "application/json"),
        )

    gemini_payload = upstream.json()
    return JSONResponse(_translate_response(gemini_payload, model))


# Expose all decisions route variants that LiteLLM's hosted_vllm/decisions
# client may append to ``api_base``, alongside the Compose healthcheck route.
app = Starlette(
    lifespan=lifespan,
    routes=[
        Route("/health", health, methods=["GET"]),
        Route("/v1/systemone", decisions, methods=["POST"]),
        Route("/v1/decisions", decisions, methods=["POST"]),
        Route("/decisions", decisions, methods=["POST"]),
    ],
)
