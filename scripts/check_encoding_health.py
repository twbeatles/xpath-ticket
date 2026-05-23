#!/usr/bin/env python3
"""Scan repository files for UTF-8 decode errors and common mojibake patterns."""

from __future__ import annotations

import argparse
import io
import os
import re
import sys
import tokenize
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
    ".pytest_tmp",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "venv",
    "__pycache__",
    "build",
    "dist",
    "htmlcov",
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
QUESTION_MARK_RUN = re.compile(r"\?{2,}")
KOREAN_MOJIBAKE_TOKENS = tuple(
    left + right
    for left, right in (
        ("뚮", "씪곗"),
        ("붿", "냼"),
        ("꾨", "젅"),
        ("덈", "룄"),
        ("몄", "뀡"),
        ("먯", "깋"),
        ("섑", "솚"),
        ("ㅽ", "뙣"),
        ("놁", "쓬"),
        ("쒕", "씪"),
        ("앹", "꽦"),
        ("곌", "껐"),
        ("묎", "렐"),
        ("곷", "젹"),
        ("쎌", "웳"),
        ("쎈", "줈"),
        ("ъ", "꽦"),
        ("곌", "낵"),
        ("곸", "쐞"),
        ("얘", "린"),
        ("뺤", "떇"),
        ("섎", "━"),
        ("깃", "났"),
        ("낅", "뜲"),
        ("댄", "듃"),
    )
)


def iter_candidate_files(root: Path) -> Iterator[Path]:
    """Yield text-like files under root while skipping ignored directories."""
    for current_root, dir_names, file_names in os.walk(root):
        dir_names[:] = [name for name in dir_names if name not in SKIP_DIRS]
        base = Path(current_root)
        for file_name in file_names:
            path = base / file_name
            if path.suffix.lower() in TEXT_SUFFIXES:
                yield path


def looks_like_mojibake(line: str, include_question_marks: bool = False) -> bool:
    if "\ufffd" in line:
        return True
    if any(token in line for token in TOKENS):
        return True
    if CP1252_HANGULISH.search(line):
        return True
    if any(token in line for token in KOREAN_MOJIBAKE_TOKENS):
        return True
    if include_question_marks and QUESTION_MARK_RUN.search(line):
        return True
    if any("\u0080" <= ch <= "\u009f" for ch in line):
        return True
    return False


def _scan_python_contexts(text: str) -> List[Tuple[int, str]]:
    """Inspect Python comments/strings only to reduce false positives."""
    suspicious: List[Tuple[int, str]] = []
    reader = io.StringIO(text).readline
    try:
        for token in tokenize.generate_tokens(reader):
            if token.type not in (tokenize.STRING, tokenize.COMMENT):
                continue
            raw = token.string
            if not looks_like_mojibake(raw, include_question_marks=True):
                continue
            snippet = raw.strip()
            if len(snippet) > 120:
                snippet = snippet[:117] + "..."
            suspicious.append((token.start[0], snippet))
    except Exception:
        return []
    return suspicious


def check_file(path: Path) -> Tuple[str | None, List[Tuple[int, str]]]:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return f"{path}: decode error ({exc})", []

    if path.suffix.lower() == ".py":
        token_hits = _scan_python_contexts(text)
        if token_hits:
            return None, token_hits

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
