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
from xpath_explorer.tools.xpath_safety import xpath_attr_equals, xpath_literal

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

class PlaywrightScanMixin:
    def _scan_page_metadata(self, page: Any) -> Dict[str, str]:
        handle = self._stable_page_handle(page)
        try:
            title = str(page.title() or "")
        except Exception:
            title = ""
        try:
            url = str(getattr(page, "url", "") or "")
        except Exception:
            url = ""
        return {"handle": handle, "title": title, "url": url}

    def _walk_scan_frames(self, page: Any) -> List[tuple[Any, str]]:
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

    def _frame_path_for_scan_frame(self, page: Any, target_frame: Any) -> str:
        for frame, frame_path in self._walk_scan_frames(page):
            if frame is target_frame:
                return frame_path
        return "main"

    def _scan_targets(self, scope: str) -> List[tuple[Any, str, Dict[str, str]]]:
        page = self._get_current_page()
        if page is None:
            return []

        normalized_scope = str(scope or "current_frame").strip().lower()
        targets: List[tuple[Any, str, Dict[str, str]]] = []

        if normalized_scope in ("current_window_frames", "current_page_frames"):
            metadata = self._scan_page_metadata(page)
            return [(frame, frame_path, metadata) for frame, frame_path in self._walk_scan_frames(page)]

        if normalized_scope in ("all_pages_frames", "all"):
            for candidate_page in self._get_open_pages():
                metadata = self._scan_page_metadata(candidate_page)
                for frame, frame_path in self._walk_scan_frames(candidate_page):
                    targets.append((frame, frame_path, metadata))
            return targets

        frame = self._get_frame()
        if frame is None:
            return []
        return [(frame, self._frame_path_for_scan_frame(page, frame), self._scan_page_metadata(page))]

    def scan_elements(
        self,
        element_type: str = 'interactive',
        max_count: int = 100,
        scope: str = "current_frame",
    ) -> List[ScannedElement]:
        """페이지 요소 자동 스캔"""
        if not self.is_alive():
            return []
            
        selector = SCAN_SELECTORS.get(element_type, SCAN_SELECTORS['interactive'])
        results = []

        with perf_span("playwright.scan_elements"):
            try:
                targets = self._scan_targets(scope)
                if not targets:
                    return []

                for frame, frame_path, window_meta in targets:
                    remaining = max(0, int(max_count) - len(results))
                    if remaining <= 0:
                        break

                    data_rows = frame.eval_on_selector_all(
                        selector,
                        """
                    (elements, maxCount) => {
                        function xpathLiteral(value) {
                            const text = String(value == null ? "" : value);
                            if (!text.includes('"')) return `"${text}"`;
                            if (!text.includes("'")) return `'${text}'`;
                            const tokens = [];
                            const parts = text.split('"');
                            for (let i = 0; i < parts.length; i++) {
                                if (parts[i]) tokens.push(`"${parts[i]}"`);
                                if (i < parts.length - 1) tokens.push("'\"'");
                            }
                            return tokens.length ? `concat(${tokens.join(", ")})` : '""';
                        }

                        function attrEquals(attr, value) {
                            return `@${attr}=${xpathLiteral(value)}`;
                        }

                        function buildXPath(el) {
                            if (!el) return "";
                            if (el.id) return `//*[${attrEquals("id", el.id)}]`;
                            const tag = (el.tagName || "").toLowerCase();
                            const name = el.getAttribute("name") || "";
                            const text = (el.innerText || "").trim();
                            if (name) return `//${tag}[${attrEquals("name", name)}]`;
                            if (text && (tag === "button" || tag === "a")) {
                                const clean = text.slice(0, 30);
                                if (clean) return `//${tag}[contains(text(), ${xpathLiteral(clean)})]`;
                            }
                            return `//${tag || "*"}`;
                        }

                        function buildCss(el) {
                            if (!el) return "";
                            const esc = (v) => (v || "").replace(/([!"#$%&'()*+,./:;<=>?@[\\\\\\]^`{|}~])/g, "\\\\$1");
                            const tag = (el.tagName || "").toLowerCase() || "*";
                            const id = el.getAttribute("id") || "";
                            const name = el.getAttribute("name") || "";
                            const klass = el.getAttribute("class") || "";

                            if (id) return `#${esc(id)}`;
                            if (name) return `${tag}[name="${(name || "").replace(/"/g, '\\"')}"]`;
                            if (klass) {
                                const classes = klass.split(/\\s+/).filter(Boolean).slice(0, 2).map(esc);
                                if (classes.length) return `${tag}.${classes.join(".")}`;
                            }
                            return tag;
                        }

                        const rows = [];
                        const slice = elements.slice(0, maxCount);
                        for (const el of slice) {
                            try {
                                const tag = (el.tagName || "").toLowerCase();
                                const text = ((el.innerText || "").trim()).slice(0, 50);
                                rows.push({
                                    tag,
                                    text,
                                    element_id: el.getAttribute("id") || "",
                                    element_name: el.getAttribute("name") || "",
                                    element_class: (el.getAttribute("class") || "").slice(0, 50),
                                    is_visible: !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length),
                                    is_enabled: !el.disabled,
                                    xpath: buildXPath(el),
                                    css_selector: buildCss(el)
                                });
                            } catch (_) {}
                        }
                        return rows;
                    }
                    """,
                        remaining
                    )

                    for row in data_rows:
                        results.append(
                            ScannedElement(
                                xpath=row.get("xpath", ""),
                                css_selector=row.get("css_selector", ""),
                                tag=row.get("tag", ""),
                                text=row.get("text", ""),
                                element_id=row.get("element_id", ""),
                                element_name=row.get("element_name", ""),
                                element_class=row.get("element_class", ""),
                                is_visible=bool(row.get("is_visible", False)),
                                is_enabled=bool(row.get("is_enabled", False)),
                                frame_path=frame_path or "main",
                                window_handle=str(window_meta.get("handle", "") or ""),
                                window_title=str(window_meta.get("title", "") or ""),
                                window_url=str(window_meta.get("url", "") or ""),
                            )
                        )

            except Exception as e:
                logger.error(f"요소 스캔 실패: {e}")

        return results

    def _generate_xpath(self, el, el_id: str, el_name: str, 
                        tag: str, text: str) -> str:
        """최적화된 XPath 생성"""
        if el_id:
            return f'//*[{xpath_attr_equals("id", el_id)}]'
        if el_name:
            return f'//{tag}[{xpath_attr_equals("name", el_name)}]'
        if text and tag in ['button', 'a']:
            clean_text = text.strip()[:30]
            if clean_text:
                return f'//{tag}[contains(text(), {xpath_literal(clean_text)})]'
        
        try:
            full_xpath = el.evaluate("""el => {
                function xpathLiteral(value) {
                    const text = String(value == null ? "" : value);
                    if (!text.includes('"')) return `"${text}"`;
                    if (!text.includes("'")) return `'${text}'`;
                    const tokens = [];
                    const parts = text.split('"');
                    for (let i = 0; i < parts.length; i++) {
                        if (parts[i]) tokens.push(`"${parts[i]}"`);
                        if (i < parts.length - 1) tokens.push("'\"'");
                    }
                    return tokens.length ? `concat(${tokens.join(", ")})` : '""';
                }
                if (el.id) return '//*[@id=' + xpathLiteral(el.id) + ']';
                var path = [];
                while (el.nodeType === Node.ELEMENT_NODE) {
                    var selector = el.nodeName.toLowerCase();
                    if (el.id) {
                        selector = '*[@id=' + xpathLiteral(el.id) + ']';
                        path.unshift('//' + selector);
                        break;
                    } else {
                        var sib = el, nth = 1;
                        while (sib = sib.previousElementSibling) {
                            if (sib.nodeName.toLowerCase() === selector) nth++;
                        }
                        if (nth !== 1) selector += '[' + nth + ']';
                    }
                    path.unshift(selector);
                    el = el.parentNode;
                }
                return '/' + path.join('/');
            }""")
            return full_xpath
        except Exception:
            return f"//{tag}"

    def _escape_css_identifier(self, value: str) -> str:
        """CSS 선택자에서 특수 문자 이스케이프"""
        if not value:
            return value
        # CSS 특수 문자 이스케이프
        return re.sub(r'([!"#$%&\'()*+,./:;<=>?@\[\\\]^`{|}~])', r'\\\1', value)

    def _generate_css_selector(self, el_id: str, el_name: str, 
                                el_class: str, tag: str) -> str:
        """CSS 셀렉터 생성 (특수문자 이스케이프 포함)"""
        if el_id:
            return f"#{self._escape_css_identifier(el_id)}"
        if el_name:
            escaped_name = el_name.replace('"', '\\"')
            return f'{tag}[name="{escaped_name}"]'
        if el_class:
            classes = el_class.split()[:2]
            escaped_classes = [self._escape_css_identifier(c) for c in classes]
            return f"{tag}.{'.'.join(escaped_classes)}"
        return tag
