# -*- coding: utf-8 -*-
"""Utilities for optional runtime imports."""

from __future__ import annotations

import importlib
import importlib.util
from typing import Any, Optional


def import_optional(module_name: str) -> Optional[Any]:
    """Import optional module safely.

    Returns imported module on success; otherwise returns ``None``.
    """
    if not module_name:
        return None

    try:
        spec = importlib.util.find_spec(module_name)
    except Exception:
        return None

    if spec is None:
        return None

    try:
        return importlib.import_module(module_name)
    except Exception:
        return None
