# -*- coding: utf-8 -*-
"""Shared storage path resolution utilities."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Optional, Tuple

APP_STORAGE_DIRNAME = ".xpath_explorer"


def _iter_storage_candidates():
    home_dir = Path.home() / APP_STORAGE_DIRNAME
    temp_dir = Path(tempfile.gettempdir()) / APP_STORAGE_DIRNAME
    yield "home", home_dir
    if temp_dir != home_dir:
        yield "temp", temp_dir


def resolve_storage_dir() -> Tuple[Optional[Path], str]:
    """
    Resolve writable storage directory.

    Order:
    1) ~/.xpath_explorer
    2) <temp>/.xpath_explorer
    3) None (in-memory only)
    """
    for source, candidate in _iter_storage_candidates():
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate, source
        except Exception:
            continue
    return None, "memory"


def resolve_storage_file(filename: str) -> Tuple[Optional[Path], str]:
    if not filename:
        return None, "memory"
    base_dir, source = resolve_storage_dir()
    if base_dir is None:
        return None, source
    return base_dir / filename, source


def atomic_write_json(path: Path, payload: Any, *, indent: int = 2, backup: bool = True) -> None:
    """Write JSON without leaving a partially-written target behind.

    Set backup=False for sensitive payloads (e.g. cookies) so no plaintext
    copy lingers next to the target.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    backup_path = target.with_suffix(f"{target.suffix}.bak")

    try:
        with open(tmp_path, "w", encoding="utf-8", newline="") as f:
            json.dump(payload, f, ensure_ascii=False, indent=indent)
            f.flush()
            os.fsync(f.fileno())

        if backup and target.exists():
            try:
                shutil.copy2(target, backup_path)
            except Exception:
                # The backup is best-effort; the atomic replace below still
                # protects the existing target from partial writes.
                pass
        tmp_path.replace(target)
    finally:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception:
            pass


def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    """Write text without leaving a partially-written target behind.

    No backup copy is kept; newline characters are preserved byte-for-byte.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target.with_name(f".{target.name}.{os.getpid()}.tmp")

    try:
        with open(tmp_path, "w", encoding=encoding, newline="") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        tmp_path.replace(target)
    finally:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception:
            pass
