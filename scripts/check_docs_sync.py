# -*- coding: utf-8 -*-
"""Document-code consistency checks for release hygiene."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple


REQUIRED_DOC_FILES: Tuple[str, ...] = (
    "README.md",
    "docs/claude.md",
    "docs/gemini.md",
)

REQUIRED_CODE_FILES: Tuple[str, ...] = (
    "xpath_explorer/main_window.py",
    "xpath_explorer/mixins/ui_mixin.py",
    "xpath_explorer/mixins/browser_mixin.py",
    "xpath_explorer/mixins/data_mixin.py",
    "xpath_explorer/mixins/tools_mixin.py",
    "xpath_explorer/ui/table_model.py",
    "xpath_explorer/ui/filter_proxy.py",
    "xpath_explorer/browser/dom_export.py",
    "xpath_explorer/browser/browser.py",
    "xpath_explorer/browser/playwright.py",
    "xpath_explorer/tools/ai.py",
    "xpath_explorer/workers/background.py",
    "xpath_explorer/runtime.py",
)

REQUIRED_TEST_FILES: Tuple[str, ...] = (
    "tests/test_batch_scenario_worker.py",
    "tests/test_error_telemetry_runtime.py",
    "tests/test_docs_sync_check.py",
)

README_REQUIRED_TOKENS: Tuple[str, ...] = (
    "xpath_explorer/main_window.py",
    "xpath_explorer/mixins/ui_mixin.py",
    "xpath_explorer/mixins/browser_mixin.py",
    "xpath_explorer/mixins/data_mixin.py",
    "xpath_explorer/mixins/tools_mixin.py",
    "xpath_explorer/ui/",
    "xpath_explorer/browser/",
    "xpath_explorer/workers/background.py",
)

DOC_REQUIRED_TOKENS: Dict[str, Tuple[str, ...]] = {
    "docs/claude.md": (
        "xpath_explorer/browser/browser.py",
        "xpath_explorer/tools/ai.py",
        "xpath_explorer/workers/background.py",
    ),
    "docs/gemini.md": (
        "xpath_explorer/browser/browser.py",
        "xpath_explorer/tools/ai.py",
        "xpath_explorer/workers/background.py",
    ),
}

TEST_REQUIRED_TOKENS: Dict[str, Tuple[str, ...]] = {
    "tests/test_batch_scenario_worker.py": (
        "BatchScenarioWorker",
        "retries",
        "retry_count",
    ),
    "tests/test_error_telemetry_runtime.py": (
        "setup_logger",
        "render_markdown_report",
    ),
    "tests/test_docs_sync_check.py": (
        "collect_findings",
        "MISSING_TOKEN",
        "MISSING_DOC_TOKEN",
        "MISSING_TEST_TOKEN",
    ),
}

LEGACY_WRAPPER_PATTERNS = {
    "README.md": (
        (
            r"`xpath_[a-z_]+\.py`",
            "README still references legacy root-level xpath_*.py modules.",
        ),
    ),
}


@dataclass(frozen=True)
class Finding:
    level: str  # ERROR | WARNING
    code: str
    target: str
    message: str


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _check_file_exists(repo_root: Path, relative_path: str, findings: List[Finding], code: str):
    if not (repo_root / relative_path).exists():
        findings.append(
            Finding(
                level="ERROR",
                code=code,
                target=relative_path,
                message="Required file does not exist.",
            )
        )


def _load_texts(repo_root: Path, paths: Sequence[str]) -> Dict[str, str]:
    texts: Dict[str, str] = {}
    for rel_path in paths:
        path = repo_root / rel_path
        if path.exists():
            texts[rel_path] = _read_text(path)
    return texts


def _check_required_tokens(
    texts: Dict[str, str],
    required_tokens_by_file: Dict[str, Tuple[str, ...]],
    findings: List[Finding],
    code: str,
):
    for rel_path, tokens in required_tokens_by_file.items():
        content = texts.get(rel_path, "")
        if not content:
            continue
        for token in tokens:
            if token not in content:
                findings.append(
                    Finding(
                        level="ERROR",
                        code=code,
                        target=rel_path,
                        message=f"Missing required token: {token}",
                    )
                )


def collect_findings(repo_root: Path) -> List[Finding]:
    findings: List[Finding] = []

    for doc in REQUIRED_DOC_FILES:
        _check_file_exists(repo_root, doc, findings, "MISSING_DOC_FILE")
    for code_file in REQUIRED_CODE_FILES:
        _check_file_exists(repo_root, code_file, findings, "MISSING_CODE_FILE")
    for test_file in REQUIRED_TEST_FILES:
        _check_file_exists(repo_root, test_file, findings, "MISSING_TEST_FILE")

    doc_texts = _load_texts(repo_root, REQUIRED_DOC_FILES)
    test_texts = _load_texts(repo_root, REQUIRED_TEST_FILES)

    _check_required_tokens(
        doc_texts,
        {"README.md": README_REQUIRED_TOKENS},
        findings,
        "MISSING_TOKEN",
    )
    _check_required_tokens(doc_texts, DOC_REQUIRED_TOKENS, findings, "MISSING_DOC_TOKEN")
    _check_required_tokens(test_texts, TEST_REQUIRED_TOKENS, findings, "MISSING_TEST_TOKEN")

    for doc, patterns in LEGACY_WRAPPER_PATTERNS.items():
        content = doc_texts.get(doc, "")
        if not content:
            continue
        for pattern, message in patterns:
            if re.search(pattern, content):
                findings.append(
                    Finding(
                        level="WARNING",
                        code="LEGACY_DESCRIPTION",
                        target=doc,
                        message=message,
                    )
                )

    return findings


def render_markdown(findings: Iterable[Finding]) -> str:
    findings = list(findings)
    errors = [f for f in findings if f.level == "ERROR"]
    warnings = [f for f in findings if f.level == "WARNING"]

    lines = [
        "# Docs Sync Check Report",
        "",
        f"- Errors: **{len(errors)}**",
        f"- Warnings: **{len(warnings)}**",
        "",
    ]
    if not findings:
        lines.append("No drift detected between docs and implementation.")
        return "\n".join(lines)

    lines.extend(
        [
            "| Level | Code | Target | Message |",
            "|---|---|---|---|",
        ]
    )
    for finding in findings:
        lines.append(
            f"| {finding.level} | {finding.code} | `{finding.target}` | {finding.message} |"
        )
    return "\n".join(lines)


def run_check(repo_root: Path, strict_warnings: bool = False) -> int:
    findings = collect_findings(repo_root)
    report = render_markdown(findings)
    print(report)

    has_errors = any(f.level == "ERROR" for f in findings)
    has_warnings = any(f.level == "WARNING" for f in findings)
    if has_errors:
        return 1
    if strict_warnings and has_warnings:
        return 1
    return 0


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check docs/code consistency.")
    default_root = Path(__file__).resolve().parents[1]
    parser.add_argument("--root", type=Path, default=default_root, help="Repository root path")
    parser.add_argument(
        "--strict-warnings",
        action="store_true",
        help="Treat warnings as failures",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Optional report file path",
    )
    args = parser.parse_args(argv)

    findings = collect_findings(args.root)
    report = render_markdown(findings)
    print(report)

    if args.report:
        args.report.write_text(report, encoding="utf-8")

    has_errors = any(f.level == "ERROR" for f in findings)
    has_warnings = any(f.level == "WARNING" for f in findings)
    if has_errors:
        return 1
    if args.strict_warnings and has_warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
