# -*- coding: utf-8 -*-
"""Browser package public exports."""

from xpath_explorer.browser.browser import BrowserManager
from xpath_explorer.browser.playwright import NetworkAnalyzer, PlaywrightManager

__all__ = [
    "BrowserManager",
    "NetworkAnalyzer",
    "PlaywrightManager",
]
