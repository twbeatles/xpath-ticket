import importlib.util
import sys
from pathlib import Path


def _load_quality_module():
    root = Path(__file__).resolve().parent.parent
    script_path = root / "scripts" / "run_quality_checks.py"
    spec = importlib.util.spec_from_file_location("run_quality_checks_module", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_quality_checks_smoke_release_runs_without_pytest_when_skip_tests(monkeypatch):
    module = _load_quality_module()
    calls = []

    def fake_run(cmd, cwd):
        calls.append(cmd)
        return 0

    monkeypatch.setattr(module, "_run", fake_run)

    code = module.main(["--skip-tests", "--smoke-release"])
    assert code == 0
    assert len(calls) == 2
    assert calls[0][1] == "scripts/check_docs_sync.py"
    assert calls[1][1] == "scripts/run_release_smoke_checks.py"


def test_quality_checks_smoke_release_runs_after_pytest(monkeypatch):
    module = _load_quality_module()
    calls = []

    def fake_run(cmd, cwd):
        calls.append(cmd)
        return 0

    monkeypatch.setattr(module, "_run", fake_run)

    code = module.main(["--smoke-release"])
    assert code == 0
    assert len(calls) == 3
    assert calls[0][1] == "scripts/check_docs_sync.py"
    assert calls[1][1] == "-m"
    assert calls[2][1] == "scripts/run_release_smoke_checks.py"

