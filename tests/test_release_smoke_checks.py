import importlib.util
import sys
from pathlib import Path


def _load_release_smoke_module():
    root = Path(__file__).resolve().parent.parent
    script_path = root / "scripts" / "run_release_smoke_checks.py"
    spec = importlib.util.spec_from_file_location("release_smoke_checks", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_check_tls_excludes_detects_libssl_and_libcrypto():
    module = _load_release_smoke_module()
    ok, blocked = module.check_tls_excludes("qt_excludes = ['libssl', 'libcrypto']")
    assert ok is False
    assert blocked == ["libcrypto", "libssl"]


def test_pyinstaller_spec_does_not_exclude_tls_libs():
    module = _load_release_smoke_module()
    root = Path(__file__).resolve().parent.parent
    spec_text = module.load_spec_text(root / "packaging" / "pyinstaller" / "xpath_explorer.spec")
    ok, blocked = module.check_tls_excludes(spec_text)
    assert ok is True
    assert blocked == []


def test_run_https_smoke_uses_https_and_accepts_2xx(monkeypatch):
    module = _load_release_smoke_module()

    class _Resp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_urlopen(request, timeout):
        assert request.full_url == "https://example.com"
        assert timeout == 1.0
        return _Resp()

    monkeypatch.setattr(module, "urlopen", fake_urlopen)
    ok, detail = module.run_https_smoke(timeout=1.0)
    assert ok is True
    assert "HTTP 200" in detail


def test_run_checks_strict_optional_imports_marks_missing_as_failure(monkeypatch):
    module = _load_release_smoke_module()
    root = Path(__file__).resolve().parent.parent

    monkeypatch.setattr(module, "run_https_smoke", lambda *args, **kwargs: (True, "ok"))
    monkeypatch.setattr(module, "run_dom_report_smoke", lambda: (True, "ok"))
    monkeypatch.setattr(
        module,
        "check_optional_imports",
        lambda: {"openai": False, "google-genai": True, "playwright": False},
    )

    results = module.run_checks(root, strict_optional_imports=True)
    optional = [r for r in results if r.name == "optional_imports"][0]
    assert optional.success is False
    assert "openai" in optional.detail
    assert "playwright" in optional.detail


def test_run_dom_report_smoke_passes():
    module = _load_release_smoke_module()
    ok, detail = module.run_dom_report_smoke()
    assert ok is True
    assert "rendered" in detail
