# -*- coding: utf-8 -*-
"""Fallback XPath generation helpers used when provider calls fail."""

from __future__ import annotations

from typing import List

from xpath_explorer.tools.xpath_safety import xpath_contains_text


def text_xpath_candidates(description: str) -> List[str]:
    text = str(description or "").strip()
    if not text:
        return []
    return [
        f"//*[{xpath_contains_text(text)}]",
        f"//button[{xpath_contains_text(text)}]",
        f"//a[{xpath_contains_text(text)}]",
    ]
