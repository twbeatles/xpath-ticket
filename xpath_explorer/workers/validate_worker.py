# -*- coding: utf-8 -*-
"""XPath Explorer worker support imports."""

import time
import logging
from typing import List, Optional, Any, Dict, cast
from threading import Event
from xpath_explorer.qt_compat import QThread, pyqtSignal

from xpath_explorer.core.config import XPathItem
from xpath_explorer.core.constants import PICKER_POLL_INTERVAL_MS, PICKER_ACTIVE_CHECK_TICKS
from xpath_explorer.tools.ai import XPathAIAssistant
from xpath_explorer.analysis.diff import XPathDiffAnalyzer
from xpath_explorer.core.perf import perf_span

logger = logging.getLogger('XPathExplorer')

from xpath_explorer.workers.worker_shared import (
    _engine_browser_for_item,
    _get_browser_frame_path,
    _get_browser_window_metadata,
    _restore_browser_context,
    _switch_browser_to_item_window,
    _window_context_from_item,
)

class ValidateWorker(QThread):
    """XPath 전체 검증 워커"""
    progress = pyqtSignal(int, str)
    validated = pyqtSignal(str, dict)
    finished = pyqtSignal(int, int)

    def __init__(self, browser: Any, items: List[XPathItem], handles: List[str], playwright: Any = None):
        super().__init__()
        self.browser = browser
        self.playwright = playwright
        self.items = items
        self.handles = handles or []
        self._stop_event = Event()

    def cancel(self):
        self._stop_event.set()

    def run(self):
        if not self.browser.is_alive():
            self.finished.emit(0, len(self.items))
            return

        original_window: Optional[str] = None
        original_frame = _get_browser_frame_path(self.browser)
        try:
            driver = getattr(self.browser, "driver", None)
            handle = getattr(driver, "current_window_handle", None)
            if isinstance(handle, str):
                original_window = handle
        except Exception as e:
            logger.warning(f"현재 윈도우 핸들 조회 실패 (계속 진행): {e}")

        total = len(self.items)
        found_total = 0
        begin_session = getattr(self.browser, "begin_validation_session", None)
        end_session = getattr(self.browser, "end_validation_session", None)
        session: Optional[Dict[str, Any]] = None
        if callable(begin_session):
            maybe_session = begin_session()
            if isinstance(maybe_session, dict):
                session = maybe_session

        try:
            for i, item in enumerate(self.items):
                if self._stop_event.is_set():
                    break

                self.progress.emit(int((i / total) * 100), f"검증 중: {item.name}")

                try:
                    engine_browser, engine_name = _engine_browser_for_item(
                        self.browser, self.playwright, item
                    )
                    if engine_browser is None:
                        self.validated.emit(
                            item.name,
                            {
                                'found': False,
                                'msg': 'Playwright 브라우저가 연결되어 있지 않습니다.',
                                'error_type': 'browser_not_connected',
                                'frame_path': getattr(item, 'found_frame', '') or '',
                                'window_handle': getattr(item, 'found_window', '') or '',
                                'window_title': getattr(item, 'found_window_title', '') or '',
                                'window_url': getattr(item, 'found_window_url', '') or '',
                            },
                        )
                        continue
                    ok, error_msg = _switch_browser_to_item_window(engine_browser, item)
                    if not ok:
                        self.validated.emit(
                            item.name,
                            {
                                'found': False,
                                'msg': error_msg,
                                'frame_path': getattr(item, 'found_frame', '') or '',
                                'window_handle': getattr(item, 'found_window', '') or '',
                                'window_title': getattr(item, 'found_window_title', '') or '',
                                'window_url': getattr(item, 'found_window_url', '') or '',
                            },
                        )
                        continue
                    item_session = session if engine_name != "playwright" else None
                    try:
                        result = cast(
                            Dict[str, Any],
                            engine_browser.validate_xpath(
                                item.xpath,
                                preferred_frame=item.found_frame or None,
                                session=item_session,
                            ),
                        )
                    except TypeError:
                        # 구 시그니처(validate_xpath(xpath)) 호환
                        result = cast(Dict[str, Any], engine_browser.validate_xpath(item.xpath))
                    if result.get('found', False):
                        found_total += 1
                    self.validated.emit(item.name, result)
                except Exception as e:
                    logger.error(f"항목 검증 실패 ({item.name}): {e}")
                    self.validated.emit(item.name, {'found': False, 'msg': str(e)})

                if self._stop_event.wait(timeout=0.1):
                    break

            self.progress.emit(100, '완료')
            self.finished.emit(found_total, total)

        finally:
            if callable(end_session):
                try:
                    end_session(session)
                except Exception:
                    pass
            self._stop_event.clear()
            if original_window is not None:
                _restore_browser_context(
                    self.browser,
                    window_handle=original_window,
                    frame_path=original_frame,
                )
