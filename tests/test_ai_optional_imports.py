import types

import pytest

import xpath_explorer.tools.ai as ai_module
from xpath_explorer.tools.ai import XPathAIAssistant


class _FakeGenerateContentConfig:
    def __init__(self, system_instruction: str, response_mime_type: str):
        self.system_instruction = system_instruction
        self.response_mime_type = response_mime_type


def test_build_gemini_generate_config_returns_none_when_module_missing(monkeypatch):
    monkeypatch.setattr(ai_module, "import_optional", lambda _name: None)

    config = XPathAIAssistant._build_gemini_generate_config("prompt")

    assert config is None


def test_build_gemini_generate_config_builds_config_when_module_exists(monkeypatch):
    fake_module = types.SimpleNamespace(GenerateContentConfig=_FakeGenerateContentConfig)
    monkeypatch.setattr(ai_module, "import_optional", lambda _name: fake_module)

    config = XPathAIAssistant._build_gemini_generate_config("prompt")

    assert isinstance(config, _FakeGenerateContentConfig)
    assert config.system_instruction == "prompt"
    assert config.response_mime_type == "application/json"


def test_get_client_openai_raises_clear_error_when_module_missing(monkeypatch):
    assistant = XPathAIAssistant(api_key="12345678901")
    assistant._provider = "openai"
    monkeypatch.setattr(ai_module, "import_optional", lambda _name: None)

    with pytest.raises(ImportError) as exc_info:
        assistant._get_client()

    assert "pip install openai" in str(exc_info.value)


def test_get_client_gemini_raises_clear_error_when_module_missing(monkeypatch):
    assistant = XPathAIAssistant(api_key="12345678901")
    assistant._provider = "gemini"
    monkeypatch.setattr(ai_module, "import_optional", lambda _name: None)

    with pytest.raises(ImportError) as exc_info:
        assistant._get_client()

    assert "pip install google-genai" in str(exc_info.value)
