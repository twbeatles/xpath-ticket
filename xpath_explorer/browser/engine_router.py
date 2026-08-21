# -*- coding: utf-8 -*-
"""Select Selenium vs Playwright engine for an XPath item."""

from __future__ import annotations

from typing import Any, Optional, Tuple


def resolve_browser_for_item(
    selenium: Any,
    playwright: Any,
    item: Any,
    *,
    fallback_selenium: bool = True,
) -> Tuple[Optional[Any], str]:
    engine = str(getattr(item, "source_engine", "") or "").strip().lower()
    if engine == "playwright":
        is_alive = getattr(playwright, "is_alive", None)
        try:
            alive = bool(is_alive()) if callable(is_alive) else False
        except Exception:
            alive = False
        if alive:
            return playwright, "playwright"
        if fallback_selenium:
            return selenium, "selenium"
        return None, "playwright"
    return selenium, "selenium"
