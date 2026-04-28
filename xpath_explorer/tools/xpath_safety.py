# -*- coding: utf-8 -*-
"""Helpers for constructing XPath expressions safely."""

from __future__ import annotations

import re
from typing import Any

_ATTR_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:-]*$")


def xpath_literal(value: Any) -> str:
    """Return an XPath string literal expression for arbitrary text."""
    text = "" if value is None else str(value)
    if '"' not in text:
        return f'"{text}"'
    if "'" not in text:
        return f"'{text}'"

    tokens: list[str] = []
    parts = text.split('"')
    for index, part in enumerate(parts):
        if part:
            tokens.append(f'"{part}"')
        if index < len(parts) - 1:
            tokens.append("'\"'")
    if not tokens:
        return '""'
    return "concat(" + ", ".join(tokens) + ")"


def is_valid_xpath_attr_name(attr_name: Any) -> bool:
    return bool(_ATTR_NAME_RE.match(str(attr_name or "")))


def xpath_attr_equals(attr_name: str, value: Any) -> str:
    """Return an equality predicate for a valid attribute name."""
    if not is_valid_xpath_attr_name(attr_name):
        raise ValueError(f"Invalid XPath attribute name: {attr_name!r}")
    return f"@{attr_name}={xpath_literal(value)}"


def xpath_attr_contains(attr_name: str, value: Any) -> str:
    """Return a contains() predicate for a valid attribute name."""
    if not is_valid_xpath_attr_name(attr_name):
        raise ValueError(f"Invalid XPath attribute name: {attr_name!r}")
    return f"contains(@{attr_name}, {xpath_literal(value)})"


def xpath_text_contains(value: Any, text_expr: str = "text()") -> str:
    """Return a contains() predicate for a text-like XPath expression."""
    return f"contains({text_expr}, {xpath_literal(value)})"


def xpath_contains_text(value: Any, text_expr: str = "text()") -> str:
    """Backward-friendly alias for text contains predicates."""
    return xpath_text_contains(value, text_expr=text_expr)
