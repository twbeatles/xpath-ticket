# -*- coding: utf-8 -*-
"""Document-code consistency checks for release hygiene."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


REQUIRED_DOC_FILES = (
    "README.md",
    "claude.md",
    "gemini.md",
)

REQUIRED_CODE_FILES = (
    "xpath 조사기(모든 티켓 사이트).py",
    "xpath_explorer/main_window.py",
    "xpath_explorer/mixins/ui_mixin.py",
    "xpath_explorer/mixins/browser_mixin.py",
    "xpath_explorer/mixins/data_mixin.py",
    "xpath_explorer/mixins/tools_mixin.py",
    "xpath_table_model.py",
    "xpath_filter_proxy.py",
    "xpath_dom_export.py",
    "xpath_browser.py",
    "xpath_playwright.py",
)

REQUIRED_TOKENS = {
    "README.md": (
        "레거시 진입점",
        "xpath_explorer/main_window.py",
        "xpath_explorer/mixins/ui_mixin.py",
        "xpath_explorer/mixins/browser_mixin.py",
        "xpath_explorer/mixins/data_mixin.py",
        "xpath_explorer/mixins/tools_mixin.py",
        "xpath_table_model.py",
        "xpath_filter_proxy.py",
        "xpath_dom_export.py",
    ),
    "claude.md": (
        "xpath_explorer/main_window.py",
        "xpath_explorer/mixins/ui_mixin.py",
        "xpath_explorer/mixins/browser_mixin.py",
        "xpath_explorer/mixins/data_mixin.py",
        "xpath_explorer/mixins/tools_mixin.py",
        "xpath_dom_export.py",
    ),
    "gemini.md": (
        "xpath_explorer/main_window.py",
        "xpath_explorer/mixins/ui_mixin.py",
        "xpath_explorer/mixins/browser_mixin.py",
        "xpath_explorer/mixins/data_mixin.py",
        "xpath_explorer/mixins/tools_mixin.py",
        "xpath_dom_export.py",
    ),
}

LEGACY_WRAPPER_PATTERNS = {
    "README.md": (
        (
            r"\|\s*`xpath 조사기\(모든 티켓 사이트\)\.py`\s*\|\s*메인 애플리케이션\s*\|",
            "레거시 진입점 파일 설명이 최신 구조와 맞지 않습니다. "
            "'레거시 진입점 래퍼'로 표기하세요.",
        ),
    )
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
                message="필수 파일이 없습니다.",
            )
        )


def collect_findings(repo_root: Path) -> List[Finding]:
    findings: List[Finding] = []

    for doc in REQUIRED_DOC_FILES:
        _check_file_exists(repo_root, doc, findings, "MISSING_DOC_FILE")
    for code_file in REQUIRED_CODE_FILES:
        _check_file_exists(repo_root, code_file, findings, "MISSING_CODE_FILE")

    doc_texts = {}
    for doc in REQUIRED_DOC_FILES:
        doc_path = repo_root / doc
        if doc_path.exists():
            doc_texts[doc] = _read_text(doc_path)

    for doc, required_tokens in REQUIRED_TOKENS.items():
        content = doc_texts.get(doc, "")
        if not content:
            continue
        for token in required_tokens:
            if token not in content:
                findings.append(
                    Finding(
                        level="ERROR",
                        code="MISSING_TOKEN",
                        target=doc,
                        message=f"필수 토큰 누락: {token}",
                    )
                )

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
        lines.append("✅ 문서-코드 정합성 체크 통과")
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


def main(argv: list[str] | None = None) -> int:
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
