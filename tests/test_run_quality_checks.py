import importlib.util
import sys
from pathlib import Path


def _load_quality_module():
    root = Path(__file__).resolve().parent.parent
    script_path = root / "scripts" / "run_quality_checks.py"
    spec = importlib.util.spec_from_file_location("run_quality_checks_module", script_path)
    assert spec is not None
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
    monkeypatch.setattr(module, "_has_pytest_cov", lambda: True)

    code = module.main(["--smoke-release"])
    assert code == 0
    assert len(calls) == 3
    assert calls[0][1] == "scripts/check_docs_sync.py"
    assert calls[1][1] == "-m"
    assert "--cov=." in calls[1]
    assert calls[2][1] == "scripts/run_release_smoke_checks.py"


def test_quality_checks_runs_plain_pytest_when_pytest_cov_missing(monkeypatch):
    module = _load_quality_module()
    calls = []

    def fake_run(cmd, cwd):
        calls.append(cmd)
        return 0

    monkeypatch.setattr(module, "_run", fake_run)
    monkeypatch.setattr(module, "_has_pytest_cov", lambda: False)

    code = module.main([])

    assert code == 0
    assert len(calls) == 2
    assert calls[1][:3] == [module.sys.executable, "-m", "pytest"]
    assert "--cov=." not in calls[1]


def test_quality_checks_no_cov_disables_coverage_even_when_available(monkeypatch):
    module = _load_quality_module()
    calls = []

    def fake_run(cmd, cwd):
        calls.append(cmd)
        return 0

    monkeypatch.setattr(module, "_run", fake_run)
    monkeypatch.setattr(module, "_has_pytest_cov", lambda: True)

    code = module.main(["--no-cov"])

    assert code == 0
    assert len(calls) == 2
    assert calls[1][:3] == [module.sys.executable, "-m", "pytest"]
    assert "--cov=." not in calls[1]


def test_quality_checks_with_pyright_runs_after_pytest(monkeypatch):
    module = _load_quality_module()
    calls = []

    def fake_run(cmd, cwd):
        calls.append(cmd)
        return 0

    monkeypatch.setattr(module, "_run", fake_run)
    monkeypatch.setattr(module, "_has_pytest_cov", lambda: True)

    code = module.main(["--with-pyright"])
    assert code == 0
    assert len(calls) == 3
    assert calls[0][1] == "scripts/check_docs_sync.py"
    assert calls[1][1] == "-m"
    assert calls[2][0] == "pyright"


def test_quality_checks_with_pyright_runs_without_pytest_when_skip_tests(monkeypatch):
    module = _load_quality_module()
    calls = []

    def fake_run(cmd, cwd):
        calls.append(cmd)
        return 0

    monkeypatch.setattr(module, "_run", fake_run)

    code = module.main(["--skip-tests", "--with-pyright"])
    assert code == 0
    assert len(calls) == 2
    assert calls[0][1] == "scripts/check_docs_sync.py"
    assert calls[1][0] == "pyright"


def test_quality_checks_with_pyright_and_smoke_release_run_in_order(monkeypatch):
    module = _load_quality_module()
    calls = []

    def fake_run(cmd, cwd):
        calls.append(cmd)
        return 0

    monkeypatch.setattr(module, "_run", fake_run)
    monkeypatch.setattr(module, "_has_pytest_cov", lambda: True)

    code = module.main(["--with-pyright", "--smoke-release"])
    assert code == 0
    assert len(calls) == 4
    assert calls[0][1] == "scripts/check_docs_sync.py"
    assert calls[1][1] == "-m"
    assert calls[2][0] == "pyright"
    assert calls[3][1] == "scripts/run_release_smoke_checks.py"


def test_quality_checks_with_pyright_failure_stops_smoke_release(monkeypatch):
    module = _load_quality_module()
    calls = []

    def fake_run(cmd, cwd):
        calls.append(cmd)
        if cmd[0] == "pyright":
            return 7
        return 0

    monkeypatch.setattr(module, "_run", fake_run)
    monkeypatch.setattr(module, "_has_pytest_cov", lambda: True)

    code = module.main(["--with-pyright", "--smoke-release"])
    assert code == 7
    assert len(calls) == 3
    assert calls[-1][0] == "pyright"


def test_quality_checks_run_returns_127_when_command_missing(tmp_path):
    module = _load_quality_module()

    code = module._run(["definitely-missing-command-for-test"], tmp_path)

    assert code == 127


def test_run_pyright_falls_back_to_python_module(monkeypatch, tmp_path):
    module = _load_quality_module()
    calls = []

    def fake_run(cmd, cwd):
        calls.append(cmd)
        if cmd == ["pyright", "-p", "."]:
            return 127
        if cmd[:4] == [sys.executable, "-m", "pyright", "-p"]:
            return 0
        return 1

    monkeypatch.setattr(module, "_run", fake_run)

    code = module._run_pyright(tmp_path)

    assert code == 0
    assert calls == [["pyright", "-p", "."], [sys.executable, "-m", "pyright", "-p", "."]]


def test_run_pyright_returns_127_when_all_commands_missing(monkeypatch, tmp_path):
    module = _load_quality_module()
    calls = []

    def fake_run(cmd, cwd):
        calls.append(cmd)
        return 127

    monkeypatch.setattr(module, "_run", fake_run)

    code = module._run_pyright(tmp_path)

    assert code == 127
    assert calls == [["pyright", "-p", "."], [sys.executable, "-m", "pyright", "-p", "."]]
