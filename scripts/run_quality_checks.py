# -*- coding: utf-8 -*-
"""Run baseline quality checks for local/dev usage."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str], cwd: Path) -> int:
    print(f"$ {' '.join(cmd)}")
    completed = subprocess.run(cmd, cwd=str(cwd), check=False)
    return completed.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run docs-sync + pytest coverage checks.")
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Run docs-sync only",
    )
    parser.add_argument(
        "--strict-doc-warnings",
        action="store_true",
        help="Treat docs-sync warnings as failures",
    )
    parser.add_argument(
        "--smoke-release",
        action="store_true",
        help="Run release smoke checks after docs/tests",
    )
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[1]

    docs_cmd = [sys.executable, "scripts/check_docs_sync.py"]
    if args.strict_doc_warnings:
        docs_cmd.append("--strict-warnings")
    code = _run(docs_cmd, repo_root)
    if code != 0:
        return code

    if args.skip_tests:
        if not args.smoke_release:
            return 0
    else:
        test_cmd = [
            sys.executable,
            "-m",
            "pytest",
            "--cov=.",
            "--cov-report=term-missing",
            "--cov-report=html",
        ]
        code = _run(test_cmd, repo_root)
        if code != 0:
            return code

    if args.smoke_release:
        smoke_cmd = [sys.executable, "scripts/run_release_smoke_checks.py"]
        code = _run(smoke_cmd, repo_root)
        if code != 0:
            return code

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
