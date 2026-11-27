"""LiteLLM proxy callbacks and compatibility patches for Junie.

Wired in via `litellm_settings.callbacks` in `config.yaml`. I use this hook
module to plug three gaps when routing Junie through `anthropic-ladder` and
`gemini-ladder`:

- Google GenAI decision routing: Upstream LiteLLM's
  `GoogleGenAIGenerateContentHandler` doesn't implement `get_structured_messages`,
  so `complexity_router` skips routing on `:generateContent` requests. Patching
  that method lets `gemini-ladder` inspect GenAI payloads and route via
  `gemini-decision-1`.
- Side-request pinning: Junie's title and task-summary side-requests get
  intercepted in `async_pre_call_hook` and pinned to `claude-haiku-5-5-low` so
  they don't pay decision-router latency or hit heavier tiers.
- Capability-filter cleanup: Small models sometimes wrap capability-filter
  selections in prose or drop an agent the user named directly. Post-call hooks
  strip the extra text and force-include any capability named in the prompt.
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
# Junie's custom Gemini models have to use `apiType: "Google"` (:generateContent
# or :streamGenerateContent) rather than `OpenAICompletion`. On LiteLLM's
# OpenAI chat surface, `embeds_thought_signature_in_tool_call_id` defaults to
# True and appends `__thought__<base64_signature>` onto `tool_call.id`, which
# breaks Junie's `spawn_subagent` tool calls in `/task-dispatcher` (and turning
# it off moves signatures into non-standard fields that fail if stripped on echo).
# Staying on `apiType: "Google"` keeps Gemini's `thoughtSignature` inside
# `content.parts[]` where it belongs.
#
# The catch is that GenAI requests carry `contents` and `systemInstruction`
# instead of OpenAI `messages`. LiteLLM's ComplexityRouter calls
# `resolve_structured_messages()`, which dispatches to
# `GoogleGenAIGenerateContentHandler.get_structured_messages()`. Upstream leaves
# that returning None, causing ComplexityRouter to log "No messages could be
# resolved, skipping routing" and bypass `gemini-decision-1`. Patching it at
# import time gives the router normalized messages without mutating the payload.
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
    """LiteLLM hook for Junie side-requests and capability-filter cleanup.

    Started out just pinning title/summary side-requests to Haiku (which is why
    `config.yaml` still imports it as `TitleRoutingHook`), and later picked up the
    capability-filter response guards too.
    """

    # System prompt prefixes sent by Junie for lightweight background side-tasks.
    # Intercepting them avoids decision-router latency/cost and prevents trivial
    # summaries from hitting higher-tier models.
    HAIKU_SYSTEM_PROMPTS = (
        "You are a chat response title creator",
        "You are a programming task description summarizer",
    )

    @classmethod
    def _matches_haiku_prompt(cls, text: str) -> bool:
        """Return True if `text` belongs to a Junie title or summary side-request."""
        return any(prompt in text for prompt in cls.HAIKU_SYSTEM_PROMPTS)

    # Junie's capability-filter agent prompt presents a numbered markdown list of
    # skills/custom agents (e.g., "1. **my-agent** - ...") and asks the model to
    # reply with a comma-separated list of matching numbers.
    CAPABILITY_FILTER_MARKER = "You are a capability filter agent"
    CAPABILITY_LINE = re.compile(r"^(\d+)\.\s+\*\*([^*]+)\*\*", re.MULTILINE)

    @staticmethod
    def _message_text(msg) -> str:
        """Pull plain text out of a string or multi-part OpenAI/Anthropic message."""
        content = msg.get("content", "")
        if isinstance(content, list):
            return " ".join(str(p.get("text", "")) for p in content if isinstance(p, dict))
        return str(content or "")

    def _forced_capabilities(self, data) -> str | None:
        """Find capability IDs explicitly named in a capability-filter prompt.

        Returns a sorted comma-separated string of required IDs (empty string when
        it's a capability-filter request with no explicit names), or `None` for normal
        traffic.
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
        """Normalize capability-filter output to sorted, comma-separated IDs.

        Walks non-empty lines bottom-up to grab the final number list (dropping
        preceding commentary), then merges in `forced`.
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
        """Strip extra prose and enforce `forced` capabilities on non-streaming responses."""
        forced = self._forced_capabilities(data)
        if forced is None:
            return response
        for choice in getattr(response, "choices", None) or []:
            message = getattr(choice, "message", None)
            if message is not None and not getattr(message, "tool_calls", None):
                message.content = self._clean_selection(message.content or "", forced)
        return response

    async def async_post_call_streaming_iterator_hook(self, user_api_key_dict, response, request_data):
        """Buffer capability-filter streams so we can rewrite and enforce `forced` IDs.

        Since a model may emit reasoning before the final number list, we collect the
        stream, put the cleaned IDs on the first content chunk, and pass remaining
        chunks through with empty content so finish/usage metadata stays intact.
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
        """Pin Junie title and summary side-requests directly to `claude-haiku-5-5-low`.

        Checks both OpenAI/Anthropic `messages` system prompts and Google GenAI
        `systemInstruction` / `system_instruction` payloads.
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
