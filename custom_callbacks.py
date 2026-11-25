import re

from litellm.google_genai.adapters.transformation import GoogleGenAIAdapter
from litellm.integrations.custom_logger import CustomLogger
from litellm.llms.gemini.google_genai.guardrail_translation.handler import (
    GoogleGenAIGenerateContentHandler,
)

_genai_adapter = GoogleGenAIAdapter()


def _google_genai_get_structured_messages(self, data: dict):
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
    HAIKU_SYSTEM_PROMPTS = (
        "You are a chat response title creator",
        "You are a programming task description summarizer",
    )

    @classmethod
    def _matches_haiku_prompt(cls, text: str) -> bool:
        return any(prompt in text for prompt in cls.HAIKU_SYSTEM_PROMPTS)

    CAPABILITY_FILTER_MARKER = "You are a capability filter agent"
    CAPABILITY_LINE = re.compile(r"^(\d+)\.\s+\*\*([^*]+)\*\*", re.MULTILINE)

    @staticmethod
    def _message_text(msg) -> str:
        content = msg.get("content", "")
        if isinstance(content, list):
            return " ".join(str(p.get("text", "")) for p in content if isinstance(p, dict))
        return str(content or "")

    def _forced_capabilities(self, data) -> str | None:
        """Return the capability-filter prompt's explicitly requested numbers, or None
        if this is not a capability filter request."""
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
        forced = {
            num for name, num in caps.items()
            if re.search(r"(?<![\w-])" + re.escape(name.strip()) + r"(?![\w-])", request)
        }
        return ",".join(str(n) for n in sorted(forced))

    @staticmethod
    def _clean_selection(text: str, forced: str) -> str:
        lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
        picked = set()
        for line in reversed(lines):
            if re.fullmatch(r"[\d\s,]+", line):
                picked = {int(x) for x in re.findall(r"\d+", line)}
                break
        picked |= {int(x) for x in forced.split(",") if x}
        return ",".join(str(n) for n in sorted(picked))

    async def async_post_call_success_hook(self, data, user_api_key_dict, response):
        forced = self._forced_capabilities(data)
        if forced is None:
            return response
        for choice in getattr(response, "choices", None) or []:
            message = getattr(choice, "message", None)
            if message is not None and not getattr(message, "tool_calls", None):
                message.content = self._clean_selection(message.content or "", forced)
        return response

    async def async_post_call_streaming_iterator_hook(self, user_api_key_dict, response, request_data):
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
