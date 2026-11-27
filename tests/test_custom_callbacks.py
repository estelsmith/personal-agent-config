"""Unit tests for litellm-proxy/custom_callbacks.py using stdlib stubs."""

from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
CUSTOM_CALLBACKS_PATH = REPO_ROOT / "litellm-proxy" / "custom_callbacks.py"


def _build_fake_litellm():
    """Create minimal `litellm` module hierarchy for importing `custom_callbacks.py`."""
    calls: list[dict] = []

    litellm_mod = types.ModuleType("litellm")

    def fake_get_llm_provider(
        model: str,
        custom_llm_provider: str | None = None,
        api_base=None,
        api_key=None,
    ):
        if custom_llm_provider is not None:
            return model, custom_llm_provider, api_key, api_base
        if "/" in model:
            provider, stripped = model.split("/", 1)
            return stripped, provider, api_key, api_base
        return model, "gemini", api_key, api_base

    litellm_mod.get_llm_provider = fake_get_llm_provider

    google_genai_mod = types.ModuleType("litellm.google_genai")
    adapters_mod = types.ModuleType("litellm.google_genai.adapters")
    transformation_mod = types.ModuleType("litellm.google_genai.adapters.transformation")

    class GoogleGenAIAdapter:
        def _transform_contents_to_messages(self, contents_list, system_instruction=None):
            msgs = [{"role": c.get("role", "user"), "content": str(c.get("parts", []))} for c in contents_list]
            if system_instruction is not None:
                msgs.insert(0, {"role": "system", "content": str(system_instruction)})
            return msgs

    transformation_mod.GoogleGenAIAdapter = GoogleGenAIAdapter

    google_genai_main_mod = types.ModuleType("litellm.google_genai.main")

    class GenerateContentHelper:
        @staticmethod
        def setup_generate_content_call(
            model: str,
            contents,
            config=None,
            custom_llm_provider: str | None = None,
            tools=None,
            **kwargs,
        ):
            record = {
                "model": model,
                "contents": contents,
                "config": config,
                "custom_llm_provider": custom_llm_provider,
                "tools": tools,
                "kwargs": kwargs,
            }
            calls.append(record)
            return record

    google_genai_main_mod.GenerateContentHelper = GenerateContentHelper

    integrations_mod = types.ModuleType("litellm.integrations")
    custom_logger_mod = types.ModuleType("litellm.integrations.custom_logger")

    class CustomLogger:
        pass

    custom_logger_mod.CustomLogger = CustomLogger

    llms_mod = types.ModuleType("litellm.llms")
    llms_gemini_mod = types.ModuleType("litellm.llms.gemini")
    llms_gemini_gg_mod = types.ModuleType("litellm.llms.gemini.google_genai")
    guardrail_mod = types.ModuleType("litellm.llms.gemini.google_genai.guardrail_translation")
    handler_mod = types.ModuleType("litellm.llms.gemini.google_genai.guardrail_translation.handler")

    class GoogleGenAIGenerateContentHandler:
        @staticmethod
        def get_structured_messages(self, data: dict):
            return None

    handler_mod.GoogleGenAIGenerateContentHandler = GoogleGenAIGenerateContentHandler

    vertex_ai_mod = types.ModuleType("litellm.llms.vertex_ai")
    vertex_gemini_mod = types.ModuleType("litellm.llms.vertex_ai.gemini")
    vertex_studio_mod = types.ModuleType(
        "litellm.llms.vertex_ai.gemini.vertex_and_google_ai_studio_gemini"
    )

    class VertexGeminiConfig:
        @staticmethod
        def _map_reasoning_effort(effort: str, model: str, reasoning_effort: object):
            include_thoughts = True
            if effort in ("disable", "none"):
                include_thoughts = False
            elif isinstance(reasoning_effort, dict) and isinstance(
                reasoning_effort.get("summary"), str
            ):
                include_thoughts = True

            if "2.5" in model:
                budgets = {"low": 1024, "medium": 8192, "high": 24576, "disable": 0, "none": 0}
                if effort not in budgets:
                    raise ValueError(f"Unsupported effort: {effort}")
                return {"thinkingBudget": budgets[effort], "includeThoughts": include_thoughts}

            if effort not in ("minimal", "low", "medium", "high", "disable", "none"):
                raise ValueError(f"Unsupported effort: {effort}")
            level = "minimal" if effort in ("disable", "none") else effort
            return {"thinkingLevel": level, "includeThoughts": include_thoughts}

    vertex_studio_mod.VertexGeminiConfig = VertexGeminiConfig

    modules = {
        "litellm": litellm_mod,
        "litellm.google_genai": google_genai_mod,
        "litellm.google_genai.adapters": adapters_mod,
        "litellm.google_genai.adapters.transformation": transformation_mod,
        "litellm.google_genai.main": google_genai_main_mod,
        "litellm.integrations": integrations_mod,
        "litellm.integrations.custom_logger": custom_logger_mod,
        "litellm.llms": llms_mod,
        "litellm.llms.gemini": llms_gemini_mod,
        "litellm.llms.gemini.google_genai": llms_gemini_gg_mod,
        "litellm.llms.gemini.google_genai.guardrail_translation": guardrail_mod,
        "litellm.llms.gemini.google_genai.guardrail_translation.handler": handler_mod,
        "litellm.llms.vertex_ai": vertex_ai_mod,
        "litellm.llms.vertex_ai.gemini": vertex_gemini_mod,
        "litellm.llms.vertex_ai.gemini.vertex_and_google_ai_studio_gemini": vertex_studio_mod,
    }
    return modules, calls, GenerateContentHelper, GoogleGenAIGenerateContentHandler


class CustomCallbacksTests(unittest.TestCase):
    """Tests for `litellm-proxy/custom_callbacks.py` patches and hooks."""

    def setUp(self) -> None:
        self._saved_modules = dict(sys.modules)
        (
            fake_modules,
            self.setup_calls,
            self.helper_cls,
            self.handler_cls,
        ) = _build_fake_litellm()
        sys.modules.update(fake_modules)

        spec = importlib.util.spec_from_file_location(
            "_test_custom_callbacks", CUSTOM_CALLBACKS_PATH
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.callbacks = module

    def tearDown(self) -> None:
        sys.modules.clear()
        sys.modules.update(self._saved_modules)

    def test_injects_thinking_level_and_preserves_include_thoughts_false(self) -> None:
        """Junie sends `thinkingConfig: {includeThoughts: false}`; add `thinkingLevel` without overwriting it."""
        original_config = {
            "stopSequences": ["</COMMAND>"],
            "thinkingConfig": {"includeThoughts": False},
        }
        result = self.helper_cls.setup_generate_content_call(
            model="gemini/gemini-4-hydrogen",
            contents=[{"role": "user", "parts": [{"text": "hello"}]}],
            config=original_config,
            custom_llm_provider="gemini",
            reasoning_effort="low",
        )
        self.assertEqual(
            result["config"],
            {
                "stopSequences": ["</COMMAND>"],
                "thinkingConfig": {"includeThoughts": False, "thinkingLevel": "low"},
            },
        )
        # Caller dict must not be mutated in place.
        self.assertEqual(original_config["thinkingConfig"], {"includeThoughts": False})

    def test_creates_thinking_config_when_client_omits_config(self) -> None:
        """When client sends `config=None`, inject `thinkingLevel` without forcing `includeThoughts: True`."""
        result = self.helper_cls.setup_generate_content_call(
            model="gemini-4-hydrogen",
            contents=[{"role": "user", "parts": [{"text": "hello"}]}],
            config=None,
            custom_llm_provider=None,
            reasoning_effort="medium",
        )
        self.assertEqual(
            result["config"],
            {"thinkingConfig": {"thinkingLevel": "medium"}},
        )

    def test_normalizes_snake_case_thinking_config(self) -> None:
        """Snake-case `thinking_config` merges cleanly into `thinkingConfig` without duplicating keys."""
        result = self.helper_cls.setup_generate_content_call(
            model="gemini/gemini-4-hydrogen",
            contents=[],
            config={"thinking_config": {"include_thoughts": False}},
            custom_llm_provider="gemini",
            reasoning_effort="high",
        )
        self.assertEqual(
            result["config"],
            {"thinkingConfig": {"include_thoughts": False, "thinkingLevel": "high"}},
        )

    def test_respects_explicit_client_thinking_overrides(self) -> None:
        """Explicit client `thinkingLevel`/`thinking_level`/`thinkingBudget` takes precedence."""
        for tc in (
            {"thinkingLevel": "high", "includeThoughts": False},
            {"thinking_level": "minimal"},
            {"thinkingBudget": 512},
            {"thinking_budget": 0},
        ):
            cfg = {"thinkingConfig": tc}
            result = self.helper_cls.setup_generate_content_call(
                model="gemini/gemini-4-hydrogen",
                contents=[],
                config=cfg,
                custom_llm_provider="gemini",
                reasoning_effort="low",
            )
            self.assertEqual(result["config"], cfg)

    def test_supports_gemini_2_5_thinking_budget(self) -> None:
        """Gemini 2.5 models map `reasoning_effort` to `thinkingBudget`."""
        result = self.helper_cls.setup_generate_content_call(
            model="gemini/gemini-2.5-pro",
            contents=[],
            config=None,
            custom_llm_provider="gemini",
            reasoning_effort="low",
        )
        self.assertEqual(
            result["config"],
            {"thinkingConfig": {"thinkingBudget": 1024}},
        )

    def test_dict_reasoning_effort_with_summary_enables_include_thoughts(self) -> None:
        """Dict `reasoning_effort` with `summary` sets `includeThoughts=True` when client omitted it."""
        result = self.helper_cls.setup_generate_content_call(
            model="gemini/gemini-4-hydrogen",
            contents=[],
            config=None,
            custom_llm_provider="gemini",
            reasoning_effort={"effort": "low", "summary": "auto"},
        )
        self.assertEqual(
            result["config"],
            {"thinkingConfig": {"thinkingLevel": "low", "includeThoughts": True}},
        )

    def test_skips_non_gemini_providers_and_missing_or_unsupported_effort(self) -> None:
        """Non-Gemini providers, missing effort, and unsupported effort values leave `config` untouched."""
        cfg = {"temperature": 0.2}
        for kwargs in (
            {"model": "anthropic/claude-sonnet-5-5", "custom_llm_provider": "anthropic", "reasoning_effort": "low"},
            {"model": "anthropic/claude-sonnet-5-5", "custom_llm_provider": None, "reasoning_effort": "low"},
            {"model": "gemini/gemini-4-hydrogen", "custom_llm_provider": "gemini"},
            {"model": "gemini/gemini-4-hydrogen", "custom_llm_provider": "gemini", "reasoning_effort": "xhigh"},
        ):
            result = self.helper_cls.setup_generate_content_call(
                contents=[],
                config=cfg,
                **kwargs,
            )
            self.assertEqual(result["config"], cfg)

    def test_google_genai_structured_messages_and_haiku_pinning(self) -> None:
        """Verify existing structured-message patch and Haiku title/summary pinning remain intact."""
        msgs = self.handler_cls().get_structured_messages(
            {
                "systemInstruction": "You are helpful.",
                "contents": [{"role": "user", "parts": [{"text": "hi"}]}],
            }
        )
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0]["role"], "system")

        hook = self.callbacks.proxy_handler_instance
        data = {
            "model": "gemini-ladder",
            "systemInstruction": {"parts": [{"text": "You are a chat response title creator."}]},
        }
        import asyncio

        updated = asyncio.run(hook.async_pre_call_hook(None, None, data, "agenerate_content"))
        self.assertEqual(updated["model"], "claude-haiku-5-5-low")


if __name__ == "__main__":
    unittest.main()
