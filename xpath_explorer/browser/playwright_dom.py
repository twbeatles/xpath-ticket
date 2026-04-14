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

class PlaywrightDomMixin:
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
                
            el.evaluate(f"""el => {{
                const original = {{
                    outline: el.style.outline,
                    outlineOffset: el.style.outlineOffset,
                    backgroundColor: el.style.backgroundColor
                }};
                el.style.outline = '3px solid #00ff88';
                el.style.outlineOffset = '2px';
                el.style.backgroundColor = 'rgba(0, 255, 136, 0.2)';
                el.scrollIntoView({{behavior: 'smooth', block: 'center'}});
                setTimeout(() => {{
                    el.style.outline = original.outline;
                    el.style.outlineOffset = original.outlineOffset;
                    el.style.backgroundColor = original.backgroundColor;
                }}, {duration_ms});
            }}""")
            return True
        except Exception as e:
            logger.error(f"하이라이트 실패: {e}")
            return False

    def validate_xpath(self, xpath: str) -> Dict:
        """XPath 검증"""
        if not self.is_alive():
            return {"found": False, "msg": "브라우저 연결 안됨"}
            
        try:
            frame = self._get_frame()
            if not frame:
                return {"found": False, "msg": "브라우저 연결 안됨"}

            elements = frame.query_selector_all(f"xpath={xpath}")
            
            if elements:
                first = elements[0]
                tag = first.evaluate("el => el.tagName.toLowerCase()")
                text = first.inner_text()[:50] if first.inner_text() else ""
                
                return {
                    "found": True,
                    "count": len(elements),
                    "tag": tag,
                    "text": text,
                    "visible": first.is_visible()
                }
            else:
                return {"found": False, "msg": "요소를 찾을 수 없음"}
                
        except Exception as e:
            return {"found": False, "msg": str(e)}
    
    # =========================================================================
    # 요소 조작
    # =========================================================================

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
    
    # =========================================================================
    # 스크린샷 및 캡처
    # =========================================================================

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

    def collect_dom_snapshots(
        self,
        include_frames: bool = True,
        scope: Literal["all", "current"] = "all",
    ) -> List[DomSnapshot]:
        """Collect DOM snapshots from open pages (popups) and frames."""
        if not self.is_alive() or not self._context:
            return []

        snapshots: List[DomSnapshot] = []
        current_page = self._get_current_page()
        root_page = self._root_page or current_page
        try:
            raw_pages = list(self._context.pages)
        except Exception:
            raw_pages = [current_page] if current_page is not None else []
        pages = raw_pages
        if scope == "current":
            pages = [current_page] if current_page is not None else []
        elif root_page and root_page in pages:
            pages = [p for p in pages if p != root_page] + [root_page]

        for page_index, page in enumerate(pages, start=1):
            window_id = f"page-{page_index}"
            is_popup = bool(root_page and page is not root_page)

            try:
                if hasattr(page, "is_closed") and page.is_closed():
                    raise Exception("page is closed")
            except Exception as e:
                error_text = str(e)
                snapshots.append(
                    DomSnapshot(
                        engine="playwright",
                        window_id=window_id,
                        window_title="",
                        window_url="",
                        is_popup=is_popup,
                        frame_path="main",
                        frame_label="main",
                        document_url="",
                        html="",
                        error=error_text,
                        error_type=self._classify_dom_error_type(error_text, page_level=True),
                    )
                )
                continue

            try:
                window_title = str(page.title() or "")
            except Exception:
                window_title = ""
            try:
                window_url = str(page.url or "")
            except Exception:
                window_url = ""

            frame_targets: List[tuple[Any, str, str]] = []

            def walk_frames(frame, path: str, label: str):
                frame_targets.append((frame, path, label))
                if not include_frames:
                    return
                try:
                    children = list(getattr(frame, "child_frames", []) or [])
                except Exception:
                    children = []
                for idx, child in enumerate(children, start=1):
                    child_name = ""
                    try:
                        child_name = str(getattr(child, "name", "") or "")
                    except Exception:
                        child_name = ""
                    identifier = child_name or f"index={idx}"
                    child_path = identifier if path in ("", "main") else f"{path}/{identifier}"
                    walk_frames(child, child_path, identifier)

            try:
                walk_frames(page.main_frame, "main", "main")
            except Exception as e:
                error_text = str(e)
                snapshots.append(
                    DomSnapshot(
                        engine="playwright",
                        window_id=window_id,
                        window_title=window_title,
                        window_url=window_url,
                        is_popup=is_popup,
                        frame_path="main",
                        frame_label="main",
                        document_url="",
                        html="",
                        error=error_text,
                        error_type=self._classify_dom_error_type(error_text, page_level=True),
                    )
                )
                continue

            if not include_frames:
                frame_targets = frame_targets[:1]

            for frame, frame_path, frame_label in frame_targets:
                doc_url = ""
                html = ""
                error_text = ""
                try:
                    try:
                        doc_url = str(getattr(frame, "url", "") or "")
                    except Exception:
                        doc_url = ""
                    html = str(
                        frame.evaluate(
                            "() => document.documentElement ? document.documentElement.outerHTML : "
                            "(document.body ? document.body.outerHTML : '')"
                        )
                        or ""
                    )
                except Exception as e:
                    error_text = str(e)

                snapshots.append(
                    DomSnapshot(
                        engine="playwright",
                        window_id=window_id,
                        window_title=window_title,
                        window_url=window_url,
                        is_popup=is_popup,
                        frame_path=frame_path or "main",
                        frame_label=frame_label or frame_path or "main",
                        document_url=doc_url,
                        html=html,
                        error=error_text,
                        error_type=self._classify_dom_error_type(error_text),
                    )
                )

        return snapshots
    
    # =========================================================================
    # iframe 처리
    # =========================================================================

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
    
    # =========================================================================
    # JavaScript 실행
    # =========================================================================

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
