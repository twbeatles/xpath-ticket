# -*- coding: utf-8 -*-
"""CSV cell sanitization helpers."""

from __future__ import annotations

from typing import Any

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def sanitize_csv_value(value: Any) -> str:
    """Neutralize spreadsheet formula injection while keeping readable text."""
    text = "" if value is None else str(value)
    if not text:
        return ""
    if text[0] in _FORMULA_PREFIXES:
        return f"'{text}"
    return text
