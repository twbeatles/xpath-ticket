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


class PlaywrightDomFrameMixin:
    def get_frames(self) -> List[Dict[str, Any]]:
        """모든 프레임 목록"""
        if not self.is_alive():
            return []
        page = self._get_current_page()
        if page is None:
            return []
        frames: List[Dict[str, Any]] = []
        for frame in page.frames:
            frames.append({
                "name": frame.name or "(unnamed)",
                "url": frame.url,
                "is_main": frame == page.main_frame
            })
        return frames

    def switch_to_frame(self, frame_name: str) -> bool:
        """특정 프레임으로 전환"""
        if not self.is_alive():
            return False

        try:
            page = self._get_current_page()
            if page is None:
                return False
            if not frame_name or frame_name == 'main':
                # 메인 프레임으로 복귀
                self._current_frame = page.main_frame
                return True

            for frame, frame_path in self._walk_frame_paths(page):
                if frame_path == frame_name:
                    self._current_frame = frame
                    logger.debug(f"프레임 전환 성공: {frame_name}")
                    return True

            # 프레임 찾기
            for frame in page.frames:
                if frame.name == frame_name or frame.url.endswith(frame_name):
                    self._current_frame = frame
                    logger.debug(f"프레임 전환 성공: {frame_name}")
                    return True

            logger.warning(f"프레임을 찾을 수 없음: {frame_name}")
            return False
        except Exception as e:
            logger.error(f"프레임 전환 실패: {e}")
            return False

    def get_current_frame(self):
        """현재 활성 프레임 반환"""
        page = self._get_current_page()
        if self._current_frame is None and page:
            return page.main_frame
        return self._current_frame

    def _get_frame(self):
        """내부 helper: 현재 프레임 (없으면 main_frame)"""
        page = self._get_current_page()
        if not page:
            return None
        return self.get_current_frame() or page.main_frame
