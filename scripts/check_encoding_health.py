#!/usr/bin/env python3
"""Scan repository files for UTF-8 decode errors and common mojibake patterns."""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Iterator, List, Sequence, Tuple


TEXT_SUFFIXES = {
    ".py",
    ".pyi",
    ".txt",
    ".md",
    ".rst",
    ".json",
    ".toml",
    ".ini",
    ".cfg",
    ".yaml",
    ".yml",
    ".xml",
    ".html",
    ".htm",
    ".css",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".bat",
    ".ps1",
    ".sh",
    ".csv",
}

SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "venv",
    "__pycache__",
    "build",
    "dist",
    "archive",
    "node_modules",
}

TOKENS = (
    "\u00c3",
    "\u00c2",
    "\u00e2\u20ac",
    "\u00e2\u20ac\u2122",
    "\u00e2\u20ac\u0153",
    "\u00e2\u20ac\u201c",
    "\u00e2\u20ac\u201d",
    "\u00e2\u20ac\u00a6",
)
CP1252_HANGULISH = re.compile(r"[\u00ec\u00ed\u00eb\u00ea][^\s]{1,4}")


def iter_candidate_files(root: Path) -> Iterator[Path]:
    """Yield text-like files under root while skipping ignored directories."""
    for current_root, dir_names, file_names in os.walk(root):
        dir_names[:] = [name for name in dir_names if name not in SKIP_DIRS]
        base = Path(current_root)
        for file_name in file_names:
            path = base / file_name
            if path.suffix.lower() in TEXT_SUFFIXES:
                yield path


def looks_like_mojibake(line: str) -> bool:
    if "\ufffd" in line:
        return True
    if any(token in line for token in TOKENS):
        return True
    if CP1252_HANGULISH.search(line):
        return True
    if any("\u0080" <= ch <= "\u009f" for ch in line):
        return True
    return False


def check_file(path: Path) -> Tuple[str | None, List[Tuple[int, str]]]:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return f"{path}: decode error ({exc})", []

    suspicious: List[Tuple[int, str]] = []
    for index, line in enumerate(text.splitlines(), start=1):
        if looks_like_mojibake(line):
            snippet = line.strip()
            if len(snippet) > 120:
                snippet = snippet[:117] + "..."
            suspicious.append((index, snippet))
    return None, suspicious


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check repository text files for UTF-8 and mojibake health."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=["."],
        help="Paths to scan (defaults to repository root).",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)
    roots = [Path(path).resolve() for path in args.paths]

    decode_errors: List[str] = []
    mojibake_hits: List[str] = []
    scanned = 0

    for root in roots:
        if not root.exists():
            decode_errors.append(f"{root}: path does not exist")
            continue
        if root.is_file():
            candidates = [root] if root.suffix.lower() in TEXT_SUFFIXES else []
        else:
            candidates = list(iter_candidate_files(root))

        for path in candidates:
            scanned += 1
            decode_error, suspicious = check_file(path)
            if decode_error:
                decode_errors.append(decode_error)
                continue
            for line_number, snippet in suspicious:
                mojibake_hits.append(f"{path}:{line_number}: {snippet}")

    for entry in decode_errors:
        print(f"[decode-fail] {entry}")
    for entry in mojibake_hits:
        print(f"[mojibake] {entry}")

    print(
        "Scanned "
        f"{scanned} files | decode failures: {len(decode_errors)} | mojibake hits: {len(mojibake_hits)}"
    )
    return 0 if not decode_errors and not mojibake_hits else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
