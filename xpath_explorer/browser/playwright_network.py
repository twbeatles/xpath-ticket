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

class PlaywrightNetworkMixin:
    def start_network_monitoring(self, filter_types: Optional[List[str]] = None):
        """네트워크 요청 모니터링 시작"""
        if not self.is_alive():
            return
        
        # 기존 리스너 정리
        self._cleanup_network_listeners()
            
        self._network_requests = []
        self._network_monitoring = True
        filter_types = filter_types or ['xhr', 'fetch', 'document']
        
        def on_request(request):
            if request.resource_type in filter_types:
                # 리스트 크기 제한
                if len(self._network_requests) >= self._max_network_requests:
                    self._network_requests.pop(0)  # 가장 오래된 요청 제거
                self._network_requests.append(NetworkRequest(
                    url=request.url,
                    method=request.method,
                    resource_type=request.resource_type
                ))
        
        def on_response(response):
            # 역방향 검색으로 최근 요청 우선 매칭 (성능 최적화)
            for req in reversed(self._network_requests):
                if req.url == response.url and req.status == 0:
                    req.status = response.status
                    try:
                        content_length = response.headers.get("content-length", "0")
                        req.response_size = int(content_length)
                    except Exception:
                        req.response_size = 0
                    break
        
        # 핸들러 참조 저장 (나중에 제거용)
        self._request_handler = on_request
        self._response_handler = on_response
        page = self._get_current_page()
        if page is None:
            return
        page.on('request', self._request_handler)
        page.on('response', self._response_handler)
        logger.info("네트워크 모니터링 시작")

    def stop_network_monitoring(self) -> List[NetworkRequest]:
        """네트워크 모니터링 중지 및 결과 반환"""
        self._cleanup_network_listeners()
        self._network_monitoring = False
        return self._network_requests.copy()

    def _cleanup_network_listeners(self):
        """네트워크 이벤트 리스너 정리"""
        page = self._get_current_page()
        if page and self._request_handler:
            try:
                page.remove_listener('request', self._request_handler)
            except Exception:
                pass
        if page and self._response_handler:
            try:
                page.remove_listener('response', self._response_handler)
            except Exception:
                pass
        self._request_handler = None
        self._response_handler = None

    def get_network_requests(self) -> List[NetworkRequest]:
        """현재까지의 네트워크 요청 목록"""
        return self._network_requests.copy()
    
    # =========================================================================
    # 쿠키 관리
    # =========================================================================
