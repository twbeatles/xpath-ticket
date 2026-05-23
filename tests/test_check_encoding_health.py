import importlib.util
import sys
from pathlib import Path


def _load_module():
    root = Path(__file__).resolve().parent.parent
    script_path = root / "scripts" / "check_encoding_health.py"
    spec = importlib.util.spec_from_file_location("check_encoding_health_module", script_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_check_file_detects_question_mark_runs_in_python_comment(tmp_path):
    module = _load_module()
    target = tmp_path / "sample.py"
    qmarks = "?" * 2
    target.write_text(f"# 깨진 문자열 {qmarks} 확인\nx = 1\n", encoding="utf-8")

    decode_error, suspicious = module.check_file(target)

    assert decode_error is None
    assert suspicious
    assert suspicious[0][0] == 1


def test_check_file_ignores_question_mark_runs_in_non_python_text(tmp_path):
    module = _load_module()
    target = tmp_path / "sample.md"
    qmarks = "?" * 2
    target.write_text(f"This is normal {qmarks} markdown punctuation.\n", encoding="utf-8")

    decode_error, suspicious = module.check_file(target)

    assert decode_error is None
    assert suspicious == []


def test_check_file_no_false_positive_on_clean_python(tmp_path):
    module = _load_module()
    target = tmp_path / "clean.py"
    target.write_text(
        'def greet(name: str) -> str:\n'
        '    return f"hello {name}"\n',
        encoding="utf-8",
    )

    decode_error, suspicious = module.check_file(target)

    assert decode_error is None
    assert suspicious == []


def test_iter_candidate_files_skips_generated_output_dirs(tmp_path):
    module = _load_module()
    good = tmp_path / "src.py"
    good.write_text("x = 1\n", encoding="utf-8")
    skipped_dir = tmp_path / ".pytest_tmp"
    skipped_dir.mkdir()
    skipped = skipped_dir / "bad.py"
    qmarks = "?" * 2
    skipped.write_text(f"# {qmarks}\n", encoding="utf-8")
    htmlcov_dir = tmp_path / "htmlcov"
    htmlcov_dir.mkdir()
    htmlcov = htmlcov_dir / "index.html"
    htmlcov.write_text("bad \ufffd\n", encoding="utf-8")

    candidates = list(module.iter_candidate_files(tmp_path))

    assert good in candidates
    assert skipped not in candidates
    assert htmlcov not in candidates


def test_check_file_detects_korean_mojibake_token(tmp_path):
    module = _load_module()
    target = tmp_path / "selenium_validation.py"
    broken = "뚮" + "씪곗" + " " + "곌" + "껐" + " " + "덈" + "맖"
    target.write_text(f"# {broken}\nx = 1\n", encoding="utf-8")

    decode_error, suspicious = module.check_file(target)

    assert decode_error is None
    assert suspicious
    assert suspicious[0][0] == 1


def test_check_file_detects_remaining_selenium_comment_mojibake(tmp_path):
    module = _load_module()
    target = tmp_path / "selenium_frames.py"
    broken = "묎" + "렐" + " " + "곷" + "젹" + " " + "쎈" + "줈"
    target.write_text(f"# {broken}\nx = 1\n", encoding="utf-8")

    decode_error, suspicious = module.check_file(target)

    assert decode_error is None
    assert suspicious
    assert suspicious[0][0] == 1
