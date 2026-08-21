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


class PlaywrightDomActionsMixin:
    def _walk_frame_paths(self, page: Any) -> List[tuple[Any, str]]:
        targets: List[tuple[Any, str]] = []

        def walk(frame: Any, path: str):
            targets.append((frame, path or "main"))
            try:
                children = list(getattr(frame, "child_frames", []) or [])
            except Exception:
                children = []
            for idx, child in enumerate(children, start=1):
                try:
                    child_name = str(getattr(child, "name", "") or "")
                except Exception:
                    child_name = ""
                identifier = child_name or f"index={idx}"
                child_path = identifier if path in ("", "main") else f"{path}/{identifier}"
                walk(child, child_path)

        try:
            walk(page.main_frame, "main")
        except Exception:
            return []
        return targets

    def highlight(self, xpath: str, duration_ms: int = 2000) -> bool:
        """요소 하이라이트"""
        if not self.is_alive():
            return False

        try:
            frame = self._get_frame()
            if not frame:
                return False

            el = frame.query_selector(f"xpath={xpath}")
            if not el:
                return False

            duration = max(0, int(duration_ms))
            el.evaluate(
                """(el, duration) => {
                const original = {
                    outline: el.style.outline,
                    outlineOffset: el.style.outlineOffset,
                    backgroundColor: el.style.backgroundColor
                };
                el.style.outline = '3px solid #00ff88';
                el.style.outlineOffset = '2px';
                el.style.backgroundColor = 'rgba(0, 255, 136, 0.2)';
                el.scrollIntoView({behavior: 'smooth', block: 'center'});
                setTimeout(() => {
                    el.style.outline = original.outline;
                    el.style.outlineOffset = original.outlineOffset;
                    el.style.backgroundColor = original.backgroundColor;
                }, duration);
            }""",
                duration,
            )
            return True
        except Exception as e:
            logger.error(f"하이라이트 실패: {e}")
            return False

    def validate_xpath(self, xpath: str) -> Dict:
        """XPath 검증"""
        if not self.is_alive():
            return {"found": False, "msg": "브라우저 연결 안됨", "error_type": "browser_not_connected"}

        try:
            frame = self._get_frame()
            if not frame:
                return {"found": False, "msg": "브라우저 연결 안됨", "error_type": "browser_not_connected"}

            elements = frame.query_selector_all(f"xpath={xpath}")
            window_meta = self.get_current_window_metadata()
            frame_path = "main"
            page = self._get_current_page()
            if page is not None:
                for candidate, candidate_path in self._walk_frame_paths(page):
                    if candidate is frame:
                        frame_path = candidate_path
                        break

            if elements:
                first = elements[0]
                tag = first.evaluate("el => el.tagName.toLowerCase()")
                text = first.inner_text()[:50] if first.inner_text() else ""

                return {
                    "found": True,
                    "count": len(elements),
                    "tag": tag,
                    "text": text,
                    "visible": first.is_visible(),
                    "frame_path": frame_path,
                    "window_handle": str(window_meta.get("handle", "") or ""),
                    "window_title": str(window_meta.get("title", "") or ""),
                    "window_url": str(window_meta.get("url", "") or ""),
                }
            else:
                return {
                    "found": False,
                    "msg": "요소를 찾을 수 없음",
                    "frame_path": frame_path,
                    "count": 0,
                    "error_type": "not_found",
                    "window_handle": str(window_meta.get("handle", "") or ""),
                    "window_title": str(window_meta.get("title", "") or ""),
                    "window_url": str(window_meta.get("url", "") or ""),
                }

        except Exception as e:
            return {"found": False, "msg": str(e), "error_type": "exception"}

    def click_element(self, xpath: str, timeout: int = 5000) -> bool:
        """요소 클릭"""
        if not self.is_alive():
            return False
        try:
            frame = self._get_frame()
            if not frame:
                return False
            frame.click(f"xpath={xpath}", timeout=timeout)
            return True
        except Exception as e:
            logger.error(f"클릭 실패: {e}")
            return False

    def fill_input(self, xpath: str, text: str, clear_first: bool = True) -> bool:
        """입력 필드에 텍스트 입력"""
        if not self.is_alive():
            return False
        try:
            frame = self._get_frame()
            if not frame:
                return False
            if clear_first:
                frame.fill(f"xpath={xpath}", text)
            else:
                frame.type(f"xpath={xpath}", text)
            return True
        except Exception as e:
            logger.error(f"입력 실패: {e}")
            return False

    def wait_for_element(
        self,
        xpath: str,
        timeout: int = 10000,
        state: Literal["attached", "detached", "hidden", "visible"] = "visible",
    ) -> bool:
        """요소 대기"""
        if not self.is_alive():
            return False
        try:
            frame = self._get_frame()
            if not frame:
                return False

            frame.wait_for_selector(f"xpath={xpath}", timeout=timeout, state=state)
            return True
        except Exception as e:
            logger.debug(f"요소 대기 실패: {e}")
            return False

    def wait_for_navigation(self, timeout: int = 30000) -> bool:
        """페이지 이동 대기"""
        if not self.is_alive():
            return False
        try:
            page = self._get_current_page()
            if page is None:
                return False
            page.wait_for_load_state('domcontentloaded', timeout=timeout)
            return True
        except Exception:
            return False

    def screenshot(self, path: Optional[str] = None, full_page: bool = False) -> Optional[bytes]:
        """스크린샷 캡처"""
        if not self.is_alive():
            return None
        try:
            page = self._get_current_page()
            if page is None:
                return None
            if path:
                return page.screenshot(path=path, full_page=full_page)
            return page.screenshot(full_page=full_page)
        except Exception as e:
            logger.error(f"스크린샷 실패: {e}")
            return None

    def capture_element(self, xpath: str, path: Optional[str] = None) -> Optional[bytes]:
        """특정 요소 캡처"""
        if not self.is_alive():
            return None
        try:
            frame = self._get_frame()
            if not frame:
                return None

            el = frame.query_selector(f"xpath={xpath}")
            if el:
                if path:
                    return el.screenshot(path=path)
                return el.screenshot()
        except Exception as e:
            logger.error(f"요소 캡처 실패: {e}")
        return None

    def save_pdf(self, path: str) -> bool:
        """페이지 PDF 저장 (headless 모드에서만 지원)"""
        if not self.is_alive():
            return False

        # PDF 저장은 headless 모드에서만 지원됨
        if not self._headless:
            logger.warning("PDF 저장은 headless 모드에서만 지원됩니다.")
            return False

        try:
            page = self._get_current_page()
            if page is None:
                return False
            page.pdf(path=path)
            return True
        except Exception as e:
            logger.error(f"PDF 저장 실패: {e}")
            return False

    def execute_script(self, script: str) -> Any:
        """JavaScript 실행"""
        if not self.is_alive():
            return None
        try:
            frame = self._get_frame()
            if not frame:
                return None
            return frame.evaluate(script)
        except Exception as e:
            logger.error(f"스크립트 실행 실패: {e}")
            return None

    def inject_script(self, script: str):
        """페이지 로드 시 스크립트 주입"""
        page = self._get_current_page()
        if page:
            page.add_init_script(script)
