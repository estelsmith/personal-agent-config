"""LiteLLM proxy custom callbacks and compatibility patches for Junie.

Registered via ``litellm_settings.callbacks: custom_callbacks.proxy_handler_instance``
in ``config.yaml``. This module addresses three integration gaps when routing Junie
traffic through LiteLLM's ``anthropic-ladder`` and ``gemini-ladder`` complexity routers:

1. **Google GenAI decision-router support**: Upstream LiteLLM's
   ``GoogleGenAIGenerateContentHandler`` does not implement
   ``get_structured_messages``, causing ``complexity_router`` to skip decision
   routing for ``apiType=Google`` (``:generateContent``) requests. Monkey-patching
   that method allows ``gemini-ladder`` to inspect Google GenAI payloads and route
   them via ``gemini-decision-1``.
2. **Junie background side-request routing**: Title-generation and task-summarization
   side-requests from Junie are intercepted in ``async_pre_call_hook`` and pinned to
   ``claude-haiku-5-5-low`` so they bypass the decision router and heavier tiers.
3. **Junie capability-filter stabilization**: Junie's capability-filter side-request
   asks an LLM to return comma-separated numbers selecting relevant skills/agents.
   Post-call hooks normalize the output format and ensure any capability explicitly
   named in the user's request is never omitted by a small/fast model.
"""

import re

from litellm.google_genai.adapters.transformation import GoogleGenAIAdapter
from litellm.integrations.custom_logger import CustomLogger
from litellm.llms.gemini.google_genai.guardrail_translation.handler import (
    GoogleGenAIGenerateContentHandler,
)

# ---------------------------------------------------------------------------
# Google GenAI -> complexity_router compatibility patch
#
# When a client uses the Google GenAI surface (:generateContent or
# :streamGenerateContent), requests carry ``contents`` and ``systemInstruction``
# instead of OpenAI ``messages``. LiteLLM's ComplexityRouter calls
# ``resolve_structured_messages()``, which dispatches to
# ``GoogleGenAIGenerateContentHandler.get_structured_messages()``. Upstream
# LiteLLM leaves that method unimplemented (inherited from BaseTranslation,
# returning None), which causes ComplexityRouter to log "No messages could be
# resolved, skipping routing" and bypass ``gemini-decision-1``.
#
# Patching ``get_structured_messages`` at import time lets the router read
# normalized OpenAI-style messages without mutating the outbound GenAI payload.
# ---------------------------------------------------------------------------

_genai_adapter = GoogleGenAIAdapter()


def _google_genai_get_structured_messages(self, data: dict):
    """Convert a Google GenAI generateContent payload into OpenAI-style messages."""
    contents = data.get("contents")
    if not contents:
        return None
    if isinstance(contents, dict):
        contents_list = [contents]
    elif isinstance(contents, str):
        contents_list = [{"role": "user", "parts": [{"text": contents}]}]
    elif isinstance(contents, list):
        contents_list = contents
    else:
        return None

    system_instruction = data.get("systemInstruction") or data.get("system_instruction")
    if isinstance(system_instruction, str):
        system_instruction = {"parts": [{"text": system_instruction}]}
    elif not isinstance(system_instruction, dict):
        system_instruction = None

    messages = _genai_adapter._transform_contents_to_messages(
        contents_list,
        system_instruction=system_instruction,
    )
    return messages or None


GoogleGenAIGenerateContentHandler.get_structured_messages = _google_genai_get_structured_messages


class TitleRoutingHook(CustomLogger):
    """LiteLLM proxy hook for Junie side-requests and capability-filter responses.

    Originally introduced to pin Junie's title/summary side-requests to Haiku
    (hence the class name, referenced by ``config.yaml``), this hook also cleans
    up and enforces constraints on Junie's capability-filter responses.
    """

    # System prompt prefixes sent by Junie for lightweight background side-tasks.
    # Intercepting them avoids paying decision-router classification latency/cost
    # or accidentally dispatching trivial summaries to higher-tier models.
    HAIKU_SYSTEM_PROMPTS = (
        "You are a chat response title creator",
        "You are a programming task description summarizer",
    )

    @classmethod
    def _matches_haiku_prompt(cls, text: str) -> bool:
        """Return True if ``text`` belongs to a Junie title/summary side-request."""
        return any(prompt in text for prompt in cls.HAIKU_SYSTEM_PROMPTS)

    # Junie's capability-filter agent prompt presents a numbered markdown list of
    # skills/custom agents (e.g., "1. **my-agent** - ...") and asks the model to
    # reply with a comma-separated list of matching numbers.
    CAPABILITY_FILTER_MARKER = "You are a capability filter agent"
    CAPABILITY_LINE = re.compile(r"^(\d+)\.\s+\*\*([^*]+)\*\*", re.MULTILINE)

    @staticmethod
    def _message_text(msg) -> str:
        """Extract plain text from a string or multi-part OpenAI/Anthropic message."""
        content = msg.get("content", "")
        if isinstance(content, list):
            return " ".join(str(p.get("text", "")) for p in content if isinstance(p, dict))
        return str(content or "")

    def _forced_capabilities(self, data) -> str | None:
        """Identify capabilities explicitly named in a capability-filter request.

        Returns a sorted, comma-separated string of capability numbers that must be
        included in the response (empty string if it *is* a capability-filter request
        but none were explicitly named), or ``None`` if this is an ordinary request.
        """
        messages = data.get("messages") or []
        texts = [self._message_text(m) for m in messages if isinstance(m, dict)]
        prompt = next((t for t in texts if self.CAPABILITY_FILTER_MARKER in t), None)
        if prompt is None:
            return None
        caps = {n: int(i) for i, n in self.CAPABILITY_LINE.findall(prompt)}
        request = " ".join(t for t in texts if t is not prompt)
        # Single-message prompts: the request follows the guidelines block.
        if not request.strip() and "</guidelines>" in prompt:
            request = prompt.rsplit("</guidelines>", 1)[1]
        # Force any capability whose exact identifier (respecting word/hyphen
        # boundaries) appears in the user's request, in case a small model omits it.
        forced = {
            num for name, num in caps.items()
            if re.search(r"(?<![\w-])" + re.escape(name.strip()) + r"(?![\w-])", request)
        }
        return ",".join(str(n) for n in sorted(forced))

    @staticmethod
    def _clean_selection(text: str, forced: str) -> str:
        """Normalize model output to sorted, comma-separated numbers plus forced IDs.

        Scans non-empty lines from bottom to top for the final number-list line
        (discarding any preceding commentary/reasoning) and merges in ``forced``.
        """
        lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
        picked = set()
        for line in reversed(lines):
            if re.fullmatch(r"[\d\s,]+", line):
                picked = {int(x) for x in re.findall(r"\d+", line)}
                break
        picked |= {int(x) for x in forced.split(",") if x}
        return ",".join(str(n) for n in sorted(picked))

    async def async_post_call_success_hook(self, data, user_api_key_dict, response):
        """Enforce forced capabilities and clean formatting on non-streaming responses."""
        forced = self._forced_capabilities(data)
        if forced is None:
            return response
        for choice in getattr(response, "choices", None) or []:
            message = getattr(choice, "message", None)
            if message is not None and not getattr(message, "tool_calls", None):
                message.content = self._clean_selection(message.content or "", forced)
        return response

    async def async_post_call_streaming_iterator_hook(self, user_api_key_dict, response, request_data):
        """Enforce forced capabilities and clean formatting on streaming responses.

        Because commentary may appear before the final number list and forced IDs
        must be merged without duplicates, capability-filter streams are buffered
        until completion, rewritten onto the first content-bearing chunk delta, and
        then yielded in order to preserve chunk framing and usage/finish metadata.
        """
        forced = self._forced_capabilities(request_data)
        if forced is None:
            async for chunk in response:
                yield chunk
            return
        chunks, text = [], ""
        async for chunk in response:
            chunks.append(chunk)
            for choice in getattr(chunk, "choices", None) or []:
                delta = getattr(choice, "delta", None)
                if delta is not None and getattr(delta, "content", None):
                    text += delta.content
        final = self._clean_selection(text, forced)
        placed = False
        for chunk in chunks:
            for choice in getattr(chunk, "choices", None) or []:
                delta = getattr(choice, "delta", None)
                if delta is not None and getattr(delta, "content", None) is not None:
                    delta.content = final if not placed else ""
                    placed = True
            yield chunk

    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        """Route Junie title/summary side-requests directly to ``claude-haiku-5-5-low``.

        Checks both OpenAI/Anthropic ``messages`` system prompts and Google GenAI
        ``systemInstruction`` / ``system_instruction`` fields (string or parts dict).
        """
        for msg in data.get("messages", []):
            if msg.get("role") == "system" and self._matches_haiku_prompt(str(msg.get("content", ""))):
                data["model"] = "claude-haiku-5-5-low"
                return data

        sys_inst = data.get("systemInstruction") or data.get("system_instruction")
        if isinstance(sys_inst, str) and self._matches_haiku_prompt(sys_inst):
            data["model"] = "claude-haiku-5-5-low"
            return data
        if isinstance(sys_inst, dict):
            parts_text = " ".join(
                str(p.get("text", "")) for p in sys_inst.get("parts", []) if isinstance(p, dict)
            )
            if self._matches_haiku_prompt(parts_text):
                data["model"] = "claude-haiku-5-5-low"
                return data

        return data


proxy_handler_instance = TitleRoutingHook()
