import importlib.util
import subprocess
import sys

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


def test_workers_import_through_qt_compat_without_pyqt6():
    script = r'''
import builtins

real_import = builtins.__import__

def blocked_import(name, *args, **kwargs):
    if name == "PyQt6" or name.startswith("PyQt6."):
        raise ImportError("blocked PyQt6")
    return real_import(name, *args, **kwargs)

builtins.__import__ = blocked_import

from xpath_explorer.workers.background import LivePreviewWorker, ValidateWorker

assert LivePreviewWorker is not None
assert ValidateWorker is not None
'''
    completed = subprocess.run(
        [sys.executable, "-c", script],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
