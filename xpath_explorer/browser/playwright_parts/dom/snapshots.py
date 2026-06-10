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


class PlaywrightDomSnapshotMixin:
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
