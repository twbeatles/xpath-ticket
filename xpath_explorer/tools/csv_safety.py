# -*- coding: utf-8 -*-
"""CSV export safety helpers."""

from __future__ import annotations

from typing import Any

FORMULA_PREFIXES = ("=", "+", "-", "@")


def sanitize_csv_cell(value: Any) -> str:
    """Prevent spreadsheet formula execution when exported CSV is opened."""
    text = "" if value is None else str(value)
    stripped = text.lstrip()
    if stripped and stripped[0] in FORMULA_PREFIXES:
        return "'" + text
    return text
