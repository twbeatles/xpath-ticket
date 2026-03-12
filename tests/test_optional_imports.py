import importlib.util

import xpath_explorer.core.optional_imports as mod


def test_import_optional_returns_none_when_spec_missing(monkeypatch):
    monkeypatch.setattr(importlib.util, "find_spec", lambda _name: None)

    result = mod.import_optional("missing.module")

    assert result is None


def test_import_optional_returns_none_when_import_fails(monkeypatch):
    monkeypatch.setattr(importlib.util, "find_spec", lambda _name: object())
    monkeypatch.setattr(mod.importlib, "import_module", lambda _name: (_ for _ in ()).throw(ImportError("x")))

    result = mod.import_optional("broken.module")

    assert result is None


def test_import_optional_returns_module_when_available(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(importlib.util, "find_spec", lambda _name: object())
    monkeypatch.setattr(mod.importlib, "import_module", lambda _name: sentinel)

    result = mod.import_optional("ok.module")

    assert result is sentinel
