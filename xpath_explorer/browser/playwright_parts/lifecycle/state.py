# -*- coding: utf-8 -*-
# pyright: reportAttributeAccessIssue=false, reportCallIssue=false, reportArgumentType=false, reportRedeclaration=false
"""
XPath Explorer - Playwright Browser Manager
Playwright 기반 브라우저 관리 및 자동 탐색 기능
탐지 우회 기술 포함
"""

import logging
import asyncio
import random
import json
import re
import subprocess
import sys
from typing import List, Dict, Optional, Any, Callable, Union, TypeAlias, Literal, Sequence, cast
from dataclasses import dataclass, field
from pathlib import Path

# 상수 임포트
from xpath_explorer.core.constants import USER_AGENTS, STEALTH_SCRIPT, SCAN_SELECTORS
from xpath_explorer.browser.dom_export import DomSnapshot
from xpath_explorer.core.perf import perf_span

logger = logging.getLogger('XPathExplorer')

PlaywrightBrowserType: TypeAlias = Any
PlaywrightBrowserContextType: TypeAlias = Any
PlaywrightPageType: TypeAlias = Any

# Playwright 가용성 확인
try:
    from playwright.sync_api import sync_playwright
    from playwright.sync_api import TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    sync_playwright = None  # type: ignore[assignment]
    PlaywrightTimeout = Exception  # type: ignore[assignment]
    logger.warning("Playwright 모듈이 설치되지 않았습니다. pip install playwright && playwright install")


from xpath_explorer.browser.playwright_models import (
    NetworkRequest,
    PlaywrightBrowserContextType,
    PlaywrightBrowserType,
    PlaywrightPageType,
    ScannedElement,
)
from xpath_explorer.browser import playwright_deps as deps

PLAYWRIGHT_AVAILABLE = deps.PLAYWRIGHT_AVAILABLE
sync_playwright = deps.sync_playwright
PlaywrightTimeout = deps.PlaywrightTimeout


class PlaywrightLifecycleStateMixin:
    def __init__(self):
        self._playwright = None
        self._browser: Optional[PlaywrightBrowserType] = None
        self._context: Optional[PlaywrightBrowserContextType] = None
        self._page: Optional[PlaywrightPageType] = None
        self._root_page: Optional[PlaywrightPageType] = None
        self._current_frame = None  # 현재 활성 프레임 컨텍스트
        self._is_initialized = False
        self._stealth_enabled = False
        self._network_requests: List[NetworkRequest] = []
        self._max_network_requests = 1000  # 네트워크 요청 제한
        self._network_monitoring = False
        self._request_handler = None
        self._response_handler = None
        self._headless = False
        self.last_error: str = ""
        self._page_ids: Dict[int, str] = {}
        self._page_id_counter = 0

    @property
    def is_available(self) -> bool:
        """Playwright 사용 가능 여부"""
        from xpath_explorer.browser import playwright as playwright_module

        return bool(playwright_module.PLAYWRIGHT_AVAILABLE)

    @property
    def page(self) -> Optional[PlaywrightPageType]:
        """현재 페이지 객체"""
        return self._get_current_page()

    def _set_current_page(self, page: Optional[PlaywrightPageType], *, make_root: bool = False):
        self._page = page
        if make_root or self._root_page is None:
            self._root_page = page
        if page is None:
            self._current_frame = None
            return
        try:
            self._current_frame = getattr(page, "main_frame", None)
        except Exception:
            self._current_frame = None
        self._stable_page_handle(page)
        self._attach_page_close_handler(page)

    def _stable_page_handle(self, page: Optional[PlaywrightPageType]) -> str:
        if page is None:
            return ""
        key = id(page)
        handle = self._page_ids.get(key)
        if handle:
            return handle
        self._page_id_counter += 1
        handle = f"pw-page-{self._page_id_counter}"
        self._page_ids[key] = handle
        return handle

    def _attach_page_close_handler(self, page: Optional[PlaywrightPageType]):
        if page is None or not hasattr(page, "on"):
            return
        try:
            page.on("close", lambda *_args, closed=page: self._handle_page_closed(closed))
        except Exception:
            pass

    def _handle_page_closed(self, closed_page: Optional[PlaywrightPageType]):
        if closed_page is None:
            return
        if self._root_page is closed_page:
            self._root_page = None
        self._page_ids.pop(id(closed_page), None)
        if self._page is not closed_page:
            return
        self._page = self._pick_fallback_page()
        if self._page is None:
            self._current_frame = None
            return
        try:
            self._current_frame = getattr(self._page, "main_frame", None)
        except Exception:
            self._current_frame = None

    def _register_context_page_tracking(self):
        if self._context is None or not hasattr(self._context, "on"):
            return
        try:
            self._context.on("page", lambda page: self._set_current_page(page))
        except Exception:
            pass

    def _get_open_pages(self) -> List[PlaywrightPageType]:
        context = self._context
        if context is None:
            return []
        try:
            pages = list(context.pages)
        except Exception:
            pages = [self._page] if self._page else []
        open_pages: List[PlaywrightPageType] = []
        for page in pages:
            try:
                if hasattr(page, "is_closed") and page.is_closed():
                    continue
            except Exception:
                continue
            open_pages.append(page)
        return open_pages

    def _pick_fallback_page(self) -> Optional[PlaywrightPageType]:
        open_pages = self._get_open_pages()
        if self._root_page in open_pages:
            root_page = self._root_page
        else:
            root_page = None
        if open_pages:
            return open_pages[-1]
        return root_page

    def _get_current_page(self) -> Optional[PlaywrightPageType]:
        page = self._page
        try:
            if page is not None and hasattr(page, "is_closed") and page.is_closed():
                page = None
        except Exception:
            page = None
        if page is None:
            page = self._pick_fallback_page()
            self._page = page
            if page is not None:
                try:
                    self._current_frame = getattr(page, "main_frame", None)
                except Exception:
                    self._current_frame = None
        return page

    @staticmethod
    def _classify_dom_error_type(error_text: str, *, page_level: bool = False) -> str:
        lowered = str(error_text or "").lower()
        if not lowered:
            return ""
        if "page is closed" in lowered or ("closed" in lowered and page_level):
            return "closed_page"
        if "detached" in lowered:
            return "detached_frame"
        if "access denied" in lowered:
            return "access_denied"
        if "cross-origin" in lowered or "cross origin" in lowered:
            return "cross_origin"
        if "frame scan" in lowered:
            return "frames_scan_failed"
        return "unknown"

    @staticmethod
    def _pick_user_agent(stealth: bool) -> str:
        """스텔스 모드에서는 Chromium과 궁합이 좋은 Windows Chrome UA를 우선 선택."""
        if not USER_AGENTS:
            return (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            )

        if stealth:
            chrome_like = [
                ua for ua in USER_AGENTS
                if "Windows NT" in ua and "Chrome/" in ua and "Firefox/" not in ua
            ]
            if chrome_like:
                return random.choice(chrome_like)

        return random.choice(USER_AGENTS)
