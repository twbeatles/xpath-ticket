# -*- coding: utf-8 -*-
# pyright: reportAttributeAccessIssue=false, reportCallIssue=false, reportArgumentType=false, reportRedeclaration=false
"""Compatibility facade for the split Playwright browser manager."""

from xpath_explorer.browser.playwright_deps import (
    PLAYWRIGHT_AVAILABLE,
    PlaywrightTimeout,
    sync_playwright,
)
from xpath_explorer.browser.playwright_dom import PlaywrightDomMixin
from xpath_explorer.browser.playwright_lifecycle import PlaywrightLifecycleMixin
from xpath_explorer.browser.playwright_models import (
    NetworkRequest,
    PlaywrightBrowserContextType,
    PlaywrightBrowserType,
    PlaywrightPageType,
    ScannedElement,
)
from xpath_explorer.browser.playwright_network import PlaywrightNetworkMixin
from xpath_explorer.browser.playwright_scan import PlaywrightScanMixin
from xpath_explorer.browser.playwright_storage import PlaywrightStorageMixin


class PlaywrightManager(
    PlaywrightLifecycleMixin,
    PlaywrightNetworkMixin,
    PlaywrightStorageMixin,
    PlaywrightScanMixin,
    PlaywrightDomMixin,
):
    """Playwright-based browser manager."""


class NetworkAnalyzer:
    """
    기존 UI와의 호환을 위한 네트워크 분석 어댑터.

    내부적으로 PlaywrightManager를 사용해 브라우저 시작/캡처/종료를 수행합니다.
    """

    def __init__(self):
        self._manager = PlaywrightManager()

    @property
    def _browser(self):
        """레거시 UI 코드와의 호환용 읽기 전용 속성."""
        return self._manager._browser

    def is_playwright_available(self) -> bool:
        return PLAYWRIGHT_AVAILABLE

    def start_browser(self, url: str, headless: bool = False) -> bool:
        if not self.is_playwright_available():
            return False
        if not self._manager.launch(headless=headless, stealth=True):
            return False
        return self._manager.navigate(url) is not False

    @property
    def last_error(self) -> str:
        return self._manager.last_error

    def start_capture(self):
        self._manager.start_network_monitoring()

    def stop_capture(self) -> list[NetworkRequest]:
        return self._manager.stop_network_monitoring()

    def close(self):
        self._manager.close()


__all__ = [
    "NetworkAnalyzer",
    "NetworkRequest",
    "PLAYWRIGHT_AVAILABLE",
    "PlaywrightBrowserContextType",
    "PlaywrightBrowserType",
    "PlaywrightManager",
    "PlaywrightPageType",
    "PlaywrightTimeout",
    "ScannedElement",
    "sync_playwright",
]
