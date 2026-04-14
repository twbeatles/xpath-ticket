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

class PlaywrightStorageMixin:
    def get_cookies(self) -> List[Dict[str, Any]]:
        """모든 쿠키 가져오기"""
        if not self._context:
            return []
        return list(cast(Any, self._context).cookies())

    def set_cookies(self, cookies: Sequence[Dict[str, Any]]):
        """쿠키 설정"""
        if self._context:
            cast(Any, self._context).add_cookies(list(cookies))

    def save_cookies(self, filepath: str):
        """쿠키를 파일로 저장"""
        cookies = self.get_cookies()
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(cookies, f, indent=2, ensure_ascii=False)
        logger.info(f"쿠키 저장됨: {filepath}")

    def load_cookies(self, filepath: str) -> bool:
        """파일에서 쿠키 로드"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
            self.set_cookies(cookies)
            logger.info(f"쿠키 로드됨: {filepath}")
            return True
        except Exception as e:
            logger.error(f"쿠키 로드 실패: {e}")
            return False

    def clear_cookies(self):
        """모든 쿠키 삭제"""
        if self._context:
            self._context.clear_cookies()
    
    # =========================================================================
    # 로컬 스토리지
    # =========================================================================

    def get_local_storage(self) -> Dict[str, Any]:
        """로컬 스토리지 가져오기"""
        if not self.is_alive():
            return {}
        try:
            page = self._page
            if page is None:
                return {}
            result = page.evaluate("() => Object.assign({}, localStorage)")
            return dict(result) if isinstance(result, dict) else {}
        except Exception:
            return {}

    def set_local_storage(self, data: Dict[str, Any]):
        """로컬 스토리지 설정 (안전한 방식)"""
        if not self.is_alive():
            return
        page = self._page
        if page is None:
            return
        # XSS 취약점 방지: 파라미터로 데이터 전달
        page.evaluate(
            "(data) => { for (const [k, v] of Object.entries(data)) localStorage.setItem(k, v); }",
            data
        )
    
    # =========================================================================
    # 자동 탐색 기능
    # =========================================================================
