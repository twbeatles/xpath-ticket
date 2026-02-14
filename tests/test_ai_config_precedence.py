import json
from pathlib import Path

import pytest

from xpath_ai import XPathAIAssistant


def _patch_home(monkeypatch, tmp_path: Path):
    # Path.home() is used inside xpath_ai.py
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
    assert a1._api_key == "file_key"  # file overrides env

    a2 = XPathAIAssistant(api_key="arg_key")
    assert a2._api_key == "arg_key"  # arg overrides everything


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

