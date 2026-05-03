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
    _get_browser_frame_path,
    _get_browser_window_metadata,
    _restore_browser_context,
    _switch_browser_to_item_window,
    _window_context_from_item,
)

class BatchTestWorker(QThread):
    """배치 테스트 워커"""
    progress = pyqtSignal(int, str)
    item_tested = pyqtSignal(str, bool, str, str)  # name, success, xpath, msg
    item_validated = pyqtSignal(str, dict)  # name, full result dict
    completed = pyqtSignal(list, bool)  # results, cancelled

    def __init__(self, browser: Any, items: List[XPathItem]):
        super().__init__()
        self.browser = browser
        self.items = items
        self._stop_event = Event()

    def cancel(self):
        self._stop_event.set()

    def run(self):
        total = len(self.items)
        results = []
        cancelled = False
        original_window = _get_browser_window_metadata(self.browser)
        original_frame = _get_browser_frame_path(self.browser)
        begin_session = getattr(self.browser, "begin_validation_session", None)
        end_session = getattr(self.browser, "end_validation_session", None)
        session: Optional[Dict[str, Any]] = None
        if callable(begin_session):
            maybe_session = begin_session()
            if isinstance(maybe_session, dict):
                session = maybe_session

        if total == 0:
            if callable(end_session):
                try:
                    end_session(session)
                except Exception:
                    pass
            self.completed.emit(results, cancelled)
            return

        try:
            for i, item in enumerate(self.items):
                if self._stop_event.is_set():
                    cancelled = True
                    break

                self.progress.emit(int((i / total) * 100), f"테스트 중: {item.name} ({i+1}/{total})")

                try:
                    result: Dict[str, Any] = {}
                    window_meta: Dict[str, Any] = {}
                    ok, error_msg = _switch_browser_to_item_window(self.browser, item)
                    if not ok:
                        success = False
                        msg = error_msg
                        result = {"error_type": "window_context", "frame_path": item.found_frame or ""}
                    else:
                        with perf_span("worker.batch_validate_loop"):
                            try:
                                result = cast(
                                    Dict[str, Any],
                                    self.browser.validate_xpath(
                                        item.xpath,
                                        preferred_frame=item.found_frame or None,
                                        session=session,
                                    ),
                                )
                            except TypeError:
                                # 구 시그니처(validate_xpath(xpath)) 호환
                                result = cast(Dict[str, Any], self.browser.validate_xpath(item.xpath))
                        success = bool(result.get('found', False))
                        msg = result.get('msg', '')
                    window_meta = _get_browser_window_metadata(self.browser)
                except Exception as e:
                    success = False
                    msg = str(e)
                    result = {}
                    window_meta = _get_browser_window_metadata(self.browser)

                row = {
                    'name': item.name,
                    'success': success,
                    'xpath': item.xpath,
                    'msg': msg,
                    'frame_path': str(result.get('frame_path', '') or item.found_frame or ''),
                    'window_handle': str(result.get('window_handle', '') or window_meta.get('handle', '') or ''),
                    'window_title': str(result.get('window_title', '') or window_meta.get('title', '') or ''),
                    'window_url': str(result.get('window_url', '') or window_meta.get('url', '') or ''),
                    'tag': str(result.get('tag', '') or ''),
                    'count': int(result.get('count', 1 if success else 0) or 0),
                    'error_type': str(result.get('error_type', '') or ''),
                }
                results.append(row)
                self.item_validated.emit(item.name, row)
                self.item_tested.emit(item.name, success, item.xpath, msg)

                if self._stop_event.wait(timeout=0.01):
                    cancelled = True
                    break
        finally:
            if callable(end_session):
                try:
                    end_session(session)
                except Exception:
                    pass
            _restore_browser_context(
                self.browser,
                window_handle=str(original_window.get('handle', '') or ''),
                frame_path=original_frame,
            )
            self.completed.emit(results, cancelled)
            self._stop_event.clear()
