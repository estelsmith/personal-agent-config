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
