import json
from pathlib import Path

import pytest

import xpath_explorer.tools.ai as ai_module
from xpath_explorer.tools.ai import XPathAIAssistant


def _patch_home(monkeypatch, tmp_path: Path):
    # Path.home() is used inside xpath_explorer/tools/ai.py
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))


def test_arg_overrides_file_and_env(monkeypatch, tmp_path):
    _patch_home(monkeypatch, tmp_path)

    monkeypatch.setenv("OPENAI_API_KEY", "env_key")

    cfg_dir = tmp_path / ".xpath_explorer"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "ai_config.json").write_text(
        json.dumps({"provider": "openai", "model": "x", "openai_api_key": "file_key"}),
        encoding="utf-8",
    )

    a1 = XPathAIAssistant()
    assert a1._provider == "openai"
    assert a1._api_key == "env_key"  # env overrides leftover file keys
    assert a1._model == "x"

    a2 = XPathAIAssistant(api_key="arg_key")
    assert a2._api_key == "arg_key"  # arg overrides everything
    assert a2._model == "x"


def test_file_key_used_when_env_missing(monkeypatch, tmp_path):
    _patch_home(monkeypatch, tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    cfg_dir = tmp_path / ".xpath_explorer"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "ai_config.json").write_text(
        json.dumps({"provider": "openai", "model": "x", "openai_api_key": "file_key"}),
        encoding="utf-8",
    )

    assistant = XPathAIAssistant()
    assert assistant._api_key == "file_key"


def test_google_api_key_is_respected_for_gemini(monkeypatch, tmp_path):
    _patch_home(monkeypatch, tmp_path)

    monkeypatch.setenv("GOOGLE_API_KEY", "google_key")

    cfg_dir = tmp_path / ".xpath_explorer"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    # provider is gemini, but no gemini_api_key in file: should fall back to env GOOGLE_API_KEY
    (cfg_dir / "ai_config.json").write_text(
        json.dumps({"provider": "gemini", "model": "gemini-flash-latest"}),
        encoding="utf-8",
    )

    a = XPathAIAssistant()
    assert a._provider == "gemini"
    assert a._api_key == "google_key"
    assert a.is_available()


def test_configure_reports_saved_result_and_persists(monkeypatch, tmp_path):
    _patch_home(monkeypatch, tmp_path)

    assistant = XPathAIAssistant()
    result = assistant.configure("sk-valid-test-key", provider="openai")

    assert result.ok is True
    assert result.config_saved is True
    assert result.storage_source == "home"
    assert assistant._model == ai_module.DEFAULT_OPENAI_MODEL

    saved = json.loads((tmp_path / ".xpath_explorer" / "ai_config.json").read_text(encoding="utf-8"))
    assert saved["provider"] == "openai"
    assert saved["model"] == ai_module.DEFAULT_OPENAI_MODEL
    assert "openai_api_key" not in saved
    assert assistant._api_key == "sk-valid-test-key"


def test_configure_uses_atomic_json_writer(monkeypatch, tmp_path):
    _patch_home(monkeypatch, tmp_path)
    calls = []

    def fake_atomic_write_json(path, payload):
        calls.append((path, payload))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(ai_module, "atomic_write_json", fake_atomic_write_json)

    assistant = XPathAIAssistant()
    result = assistant.configure("sk-valid-test-key", provider="openai")

    assert result.config_saved is True
    assert calls
    assert calls[0][0].name == "ai_config.json"


def test_configure_reports_runtime_only_when_storage_unavailable(monkeypatch):
    monkeypatch.setattr(ai_module, "resolve_storage_file", lambda _filename: (None, "memory"))

    assistant = XPathAIAssistant()
    result = assistant.configure("sk-valid-test-key", provider="openai")

    assert result.ok is True
    assert result.config_saved is False
    assert result.storage_source == "memory"
    assert "현재 세션" in result.message


def test_configure_rejects_invalid_key():
    assistant = XPathAIAssistant()

    result = assistant.configure("short", provider="openai")

    assert result.ok is False
    assert result.config_saved is False
    assert "API 키" in result.message

