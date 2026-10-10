# -*- coding: utf-8 -*-
"""Crash-recovery autosave helpers (Phase 2) tests."""

import json
from pathlib import Path

from xpath_explorer.core import autosave as autosave_module
from xpath_explorer.core.config import SiteConfig


def _patch_home(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))


def _config_with_items():
    config = SiteConfig.from_preset("빈 템플릿")
    return config


def test_write_and_read_autosave_roundtrip(monkeypatch, tmp_path):
    _patch_home(monkeypatch, tmp_path)
    config = _config_with_items()

    assert autosave_module.write_autosave(config) is True

    payload = autosave_module.read_autosave()
    assert payload is not None
    assert payload["config"]["name"] == config.name
    assert "saved_at" in payload


def test_read_autosave_missing_returns_none(monkeypatch, tmp_path):
    _patch_home(monkeypatch, tmp_path)

    assert autosave_module.read_autosave() is None


def test_read_autosave_corrupt_returns_none(monkeypatch, tmp_path):
    _patch_home(monkeypatch, tmp_path)
    cfg_dir = tmp_path / ".xpath_explorer"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "autosave.json").write_text("not-json{{{", encoding="utf-8")

    assert autosave_module.read_autosave() is None


def test_is_autosave_restorable_detects_difference(monkeypatch, tmp_path):
    _patch_home(monkeypatch, tmp_path)
    config = _config_with_items()
    assert autosave_module.write_autosave(config) is True

    payload = autosave_module.read_autosave()
    assert payload is not None
    assert autosave_module.is_autosave_restorable(config, payload) is False

    config.name = "changed"
    assert autosave_module.is_autosave_restorable(config, payload) is True


def test_clear_autosave_removes_file(monkeypatch, tmp_path):
    _patch_home(monkeypatch, tmp_path)
    assert autosave_module.write_autosave(_config_with_items()) is True
    path = autosave_module.autosave_path()
    assert path is not None
    assert path.exists()

    autosave_module.clear_autosave()

    assert not path.exists()
    assert autosave_module.read_autosave() is None


def test_autosave_payload_restores_through_site_config(monkeypatch, tmp_path):
    _patch_home(monkeypatch, tmp_path)
    from xpath_explorer.core.config import XPathItem

    config = _config_with_items()
    config.add_or_update(XPathItem(name="n1", xpath="//a", category="common"))
    assert autosave_module.write_autosave(config) is True

    payload = autosave_module.read_autosave()
    assert payload is not None
    restored = SiteConfig.from_dict(payload["config"])
    assert restored.get_item("n1") is not None
    assert json.loads(json.dumps(payload["config"]))["items"][0]["name"] == "n1"
