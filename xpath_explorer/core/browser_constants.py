# -*- coding: utf-8 -*-
"""Compatibility facade for browser constants and script assets."""

from xpath_explorer.core.browser_assets.picker import PICKER_SCRIPT
from xpath_explorer.core.browser_assets.scan import SCAN_SELECTORS
from xpath_explorer.core.browser_assets.stealth import STEALTH_SCRIPT, USER_AGENTS
from xpath_explorer.core.browser_assets.timing import (
    BROWSER_CHECK_INTERVAL,
    DEFAULT_WINDOW_SIZE,
    FRAME_CACHE_DURATION,
    LIVE_PREVIEW_DEBOUNCE_MS,
    MAX_FRAME_DEPTH,
    PICKER_ACTIVE_CHECK_TICKS,
    PICKER_POLL_INTERVAL_MS,
    SEARCH_DEBOUNCE_MS,
    VALIDATION_MISS_TTL_SECONDS,
    WORKER_WAIT_TIMEOUT,
)

__all__ = [
    "BROWSER_CHECK_INTERVAL",
    "DEFAULT_WINDOW_SIZE",
    "FRAME_CACHE_DURATION",
    "LIVE_PREVIEW_DEBOUNCE_MS",
    "MAX_FRAME_DEPTH",
    "PICKER_ACTIVE_CHECK_TICKS",
    "PICKER_POLL_INTERVAL_MS",
    "PICKER_SCRIPT",
    "SCAN_SELECTORS",
    "SEARCH_DEBOUNCE_MS",
    "STEALTH_SCRIPT",
    "USER_AGENTS",
    "VALIDATION_MISS_TTL_SECONDS",
    "WORKER_WAIT_TIMEOUT",
]
