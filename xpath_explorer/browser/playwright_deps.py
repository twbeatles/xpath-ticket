# -*- coding: utf-8 -*-
"""Playwright runtime dependency seam."""

import logging

logger = logging.getLogger("XPathExplorer")

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeout
    from playwright.sync_api import sync_playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    sync_playwright = None  # type: ignore[assignment]
    PlaywrightTimeout = Exception  # type: ignore[assignment]
    logger.warning(
        "Playwright is not installed. Run: pip install playwright && playwright install"
    )
