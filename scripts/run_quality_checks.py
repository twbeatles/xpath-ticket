# -*- coding: utf-8 -*-
"""Run baseline quality checks for local/dev usage."""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str], cwd: Path) -> int:
    print(f"$ {' '.join(cmd)}")
    try:
        completed = subprocess.run(cmd, cwd=str(cwd), check=False)
    except FileNotFoundError as e:
        print(f"Command not found: {cmd[0]} ({e})")
        return 127
    return completed.returncode


def _run_pyright(cwd: Path) -> int:
    """Run pyright with fallback to python -m pyright."""
    code = _run(["pyright"], cwd)
    if code != 127:
        return code

    fallback_cmd = [sys.executable, "-m", "pyright"]
    code = _run(fallback_cmd, cwd)
    if code != 0:
        print("Pyright is not available. Install dev deps: pip install -r requirements/requirements-dev.txt")
    return code


def _has_pytest_cov() -> bool:
    return importlib.util.find_spec("pytest_cov") is not None


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
    parser.add_argument(
        "--with-pyright",
        action="store_true",
        help="Run pyright type checks after docs/tests",
    )
    parser.add_argument(
        "--no-cov",
        action="store_true",
        help="Run pytest without coverage even if pytest-cov is installed.",
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
        if not args.with_pyright and not args.smoke_release:
            return 0
    else:
        test_cmd = [
            sys.executable,
            "-m",
            "pytest",
        ]
        enable_coverage = (not args.no_cov) and _has_pytest_cov()
        if enable_coverage:
            test_cmd.extend(
                [
                    "--cov=.",
                    "--cov-report=term-missing",
                    "--cov-report=html",
                ]
            )
        elif not args.no_cov:
            print("pytest-cov not found; running pytest without coverage.")
        code = _run(test_cmd, repo_root)
        if code != 0:
            return code

    if args.with_pyright:
        code = _run_pyright(repo_root)
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
