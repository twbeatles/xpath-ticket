import importlib.util
import sys
from pathlib import Path


def _load_docs_sync_module():
    root = Path(__file__).resolve().parent.parent
    script_path = root / "scripts" / "check_docs_sync.py"
    spec = importlib.util.spec_from_file_location("docs_sync_check", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_docs_sync_check_passes_current_repo():
    module = _load_docs_sync_module()
    root = Path(__file__).resolve().parent.parent
    findings = module.collect_findings(root)
    errors = [f for f in findings if f.level == "ERROR"]
    assert errors == []


def test_docs_sync_check_detects_missing_required_tokens(tmp_path: Path):
    module = _load_docs_sync_module()

    for rel in module.REQUIRED_DOC_FILES:
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# minimal\n", encoding="utf-8")

    for rel in module.REQUIRED_CODE_FILES:
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")

    for rel in module.REQUIRED_TEST_FILES:
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# minimal\n", encoding="utf-8")

    findings = module.collect_findings(tmp_path)
    errors = [f for f in findings if f.level == "ERROR"]
    assert errors
    assert any(f.code == "MISSING_TOKEN" and f.target == "README.md" for f in errors)
    assert any(f.code == "MISSING_DOC_TOKEN" and f.target == "docs/claude.md" for f in errors)
    assert any(f.code == "MISSING_DOC_TOKEN" and f.target == "docs/gemini.md" for f in errors)
    assert any(f.code == "MISSING_TEST_TOKEN" and f.target == "tests/test_batch_scenario_worker.py" for f in errors)
