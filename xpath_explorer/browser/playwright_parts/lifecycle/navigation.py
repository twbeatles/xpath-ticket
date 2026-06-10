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


class PlaywrightNavigationMixin:
    def is_alive(self) -> bool:
        """연결 상태 확인"""
        if not self._is_initialized:
            return False
        try:
            page = self._get_current_page()
            if page is None:
                return False
            page.evaluate("() => true")
            if self._current_frame is None:
                try:
                    self._current_frame = getattr(page, "main_frame", None)
                except Exception:
                    self._current_frame = None
            return True
        except Exception:
            self._page = self._pick_fallback_page()
            self._current_frame = None
            fallback = self._page
            if fallback is None:
                return False
            try:
                fallback.evaluate("() => true")
                self._current_frame = getattr(fallback, "main_frame", None)
                return True
            except Exception:
                return False

    def navigate(
        self,
        url: str,
        timeout: int = 30000,
        wait_until: Literal["commit", "domcontentloaded", "load", "networkidle"] = "domcontentloaded",
    ) -> Union[bool, None]:
        """
        URL 이동

        Returns:
            True: 성공
            None: 타임아웃 (부분 성공 가능)
            False: 실패
        """
        if not self.is_alive():
            return False
        try:
            page = self._get_current_page()
            if page is None:
                return False
            page.goto(url, timeout=timeout, wait_until=wait_until)
            return True
        except PlaywrightTimeout:
            logger.warning(f"페이지 로딩 타임아웃: {url}")
            return None  # 타임아웃은 부분 성공일 수 있음
        except Exception as e:
            logger.error(f"페이지 이동 실패: {e}")
            return False

    def get_current_url(self) -> str:
        """현재 URL 반환"""
        page = self._get_current_page()
        if page:
            return page.url
        return ""

    def get_page_title(self) -> str:
        """현재 페이지 제목"""
        page = self._get_current_page()
        if page:
            return page.title()
        return ""

    def get_current_window_metadata(self) -> Dict[str, Any]:
        page = self._get_current_page()
        if page is None:
            return {"handle": "", "title": "", "url": "", "is_popup": False}
        try:
            title = str(page.title() or "")
        except Exception:
            title = ""
        try:
            url = str(page.url or "")
        except Exception:
            url = ""
        handle = self._stable_page_handle(page)
        root_page = self._root_page or page
        return {
            "handle": handle,
            "title": title,
            "url": url,
            "is_popup": bool(root_page and page is not root_page),
        }
