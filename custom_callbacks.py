from litellm.integrations.custom_logger import CustomLogger


class TitleRoutingHook(CustomLogger):
    HAIKU_SYSTEM_PROMPTS = (
        "You are a chat response title creator",
        "You are a programming task description summarizer",
    )

    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        for msg in data.get("messages", []):
            if msg.get("role") == "system":
                content = str(msg.get("content", ""))
                if any(prompt in content for prompt in self.HAIKU_SYSTEM_PROMPTS):
                    data["model"] = "claude-haiku-5-5-low"
                    break
        return data


proxy_handler_instance = TitleRoutingHook()
