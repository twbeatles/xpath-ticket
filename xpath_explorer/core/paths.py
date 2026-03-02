# -*- coding: utf-8 -*-
"""Shared storage path resolution utilities."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Optional, Tuple

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

