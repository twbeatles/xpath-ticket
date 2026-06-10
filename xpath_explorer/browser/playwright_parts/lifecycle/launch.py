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


class PlaywrightLaunchMixin:
    def launch(self, headless: bool = False, stealth: bool = True) -> bool:
        """
        브라우저 실행 (탐지 우회 옵션)

        Args:
            headless: 헤드리스 모드
            stealth: 탐지 우회 활성화
        """
        from xpath_explorer.browser import playwright as playwright_module

        if not playwright_module.PLAYWRIGHT_AVAILABLE:
            logger.error("Playwright가 설치되지 않았습니다.")
            self.last_error = "Playwright is not installed"
            return False

        self.last_error = ""

        # Playwright sync API는 실행 중인 asyncio loop 내부에서 동작하지 않는다.
        try:
            running_loop = asyncio.get_running_loop()
            if running_loop.is_running():
                self.last_error = "sync_playwright cannot run inside an active asyncio loop"
                logger.error(
                    "Playwright Sync API는 asyncio 루프 내부에서 실행할 수 없습니다. "
                    "현재 경로는 Async API 또는 별도 스레드/프로세스가 필요합니다."
                )
                return False
        except RuntimeError:
            # 현재 스레드에 실행 중 asyncio loop 없음 (정상)
            pass

        try:
            # 랜덤 User-Agent 선택 (stealth 모드에서는 Chrome 계열 우선)
            user_agent = self._pick_user_agent(stealth)
            if sync_playwright is None:
                self.last_error = "sync_playwright is unavailable"
                return False
            self._playwright = playwright_module.sync_playwright().start()

            # 브라우저 시작 옵션
            launch_args = [
                '--start-maximized',
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-infobars',
                '--disable-extensions',
                '--lang=ko-KR',
            ]

            if headless:
                launch_args.extend([
                    '--headless=new',  # 새로운 headless 모드 (탐지 어려움)
                ])

            launch_kwargs = {
                "headless": headless,
                "args": launch_args,
                "ignore_default_args": ["--enable-automation"],
            }

            # 가능한 경우 시스템 Chrome 채널 우선 사용 (탐지 회피에 유리)
            self._browser = None
            if stealth:
                try:
                    self._browser = self._playwright.chromium.launch(channel="chrome", **launch_kwargs)
                    logger.info("Playwright system Chrome 채널로 실행")
                except Exception as e:
                    logger.debug(f"system Chrome 채널 실행 실패, bundled Chromium으로 폴백: {e}")

            if self._browser is None:
                self._browser = self._playwright.chromium.launch(**launch_kwargs)
            self._headless = headless
            if self._browser is None:
                self.last_error = "browser launch failed"
                return False

            # 컨텍스트 생성 (fingerprint 설정)
            self._context = self._browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent=user_agent,
                locale='ko-KR',
                timezone_id='Asia/Seoul',
                geolocation={'latitude': 37.5665, 'longitude': 126.9780},
                permissions=['geolocation'],
                color_scheme='light',
                device_scale_factor=1,
                extra_http_headers={
                    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Upgrade-Insecure-Requests": "1",
                },
            )
            if self._context is None:
                self.last_error = "browser context creation failed"
                return False

            page = self._context.new_page()
            if page is None:
                self.last_error = "page creation failed"
                return False
            self._set_current_page(page, make_root=True)
            self._register_context_page_tracking()

            # 탐지 우회 스크립트 주입
            if stealth:
                self._apply_stealth()

            self._is_initialized = True
            self._stealth_enabled = stealth
            logger.info(f"Playwright 브라우저 실행 완료 (stealth={stealth})")
            return True

        except Exception as e:
            self.last_error = str(e)
            logger.error(f"Playwright 브라우저 실행 실패: {e}")
            try:
                self.close()
            except Exception as cleanup_error:
                logger.debug(f"Playwright 초기화 실패 후 정리 중 예외(무시): {cleanup_error}")
            return False

    def _apply_stealth(self):
        """탐지 우회 스크립트 적용"""
        # 모든 페이지/팝업/프레임에 적용되도록 context 기준으로 init script 주입
        if self._context:
            self._context.add_init_script(STEALTH_SCRIPT)

        # 이미 열린 현재 페이지에도 즉시 적용
        if self._page:
            try:
                self._page.evaluate(STEALTH_SCRIPT)
            except Exception:
                pass

        logger.debug("Stealth 스크립트 적용됨")

    def close(self):
        """브라우저 종료 (안전한 리소스 정리)"""
        # 1. 네트워크 리스너 먼저 정리
        try:
            self._cleanup_network_listeners()
        except Exception as e:
            logger.debug(f"네트워크 리스너 정리 중 예외: {e}")

        # 2. 컨텍스트 종료
        try:
            if self._context:
                self._context.close()
        except Exception as e:
            logger.debug(f"컨텍스트 종료 중 예외: {e}")

        # 3. 브라우저 종료
        try:
            if self._browser:
                self._browser.close()
        except Exception as e:
            logger.debug(f"브라우저 종료 중 예외: {e}")

        # 4. Playwright 인스턴스 종료
        try:
            if self._playwright:
                self._playwright.stop()
        except Exception as e:
            logger.debug(f"Playwright 종료 중 예외: {e}")

        # 5. 상태 초기화 (finally 역할)
        self._page = None
        self._root_page = None
        self._context = None
        self._browser = None
        self._playwright = None
        self._is_initialized = False
        self._network_requests = []
        self._current_frame = None
        self._page_ids = {}
        self._page_id_counter = 0
