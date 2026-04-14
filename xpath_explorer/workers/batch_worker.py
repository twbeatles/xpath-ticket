# -*- coding: utf-8 -*-
"""XPath Explorer worker support imports."""

import time
import logging
from typing import List, Optional, Any, Dict, cast
from threading import Event
from PyQt6.QtCore import QThread, pyqtSignal

from xpath_explorer.core.config import XPathItem
from xpath_explorer.core.constants import PICKER_POLL_INTERVAL_MS, PICKER_ACTIVE_CHECK_TICKS
from xpath_explorer.tools.ai import XPathAIAssistant
from xpath_explorer.analysis.diff import XPathDiffAnalyzer
from xpath_explorer.core.perf import perf_span

logger = logging.getLogger('XPathExplorer')

from xpath_explorer.workers.worker_shared import (
    _get_browser_window_metadata,
    _switch_browser_to_item_window,
    _window_context_from_item,
)

class BatchTestWorker(QThread):
    """배치 테스트 워커"""
    progress = pyqtSignal(int, str)
    item_tested = pyqtSignal(str, bool, str, str)  # name, success, xpath, msg
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
                    ok, error_msg = _switch_browser_to_item_window(self.browser, item)
                    if not ok:
                        success = False
                        msg = error_msg
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
                        success = result.get('found', False)
                        msg = result.get('msg', '')
                except Exception as e:
                    success = False
                    msg = str(e)

                row = {
                    'name': item.name,
                    'success': success,
                    'xpath': item.xpath,
                    'msg': msg,
                    'window_handle': str(_get_browser_window_metadata(self.browser).get('handle', '') or ''),
                    'window_title': str(_get_browser_window_metadata(self.browser).get('title', '') or ''),
                }
                results.append(row)
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
            self.completed.emit(results, cancelled)
            self._stop_event.clear()
