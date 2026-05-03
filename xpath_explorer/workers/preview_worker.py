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

class LivePreviewWorker(QThread):
    """실시간 미리보기용 요소 카운트 워커."""
    counted = pyqtSignal(int, int)  # request_id, count
    failed = pyqtSignal(int, str)   # request_id, error

    def __init__(
        self,
        browser: Any,
        xpath: str,
        request_id: int,
        frame_path: Optional[str] = None,
        window_context: Optional[Dict[str, Any]] = None,
    ):
        super().__init__()
        self.browser = browser
        self.xpath = xpath
        self.request_id = request_id
        self.frame_path = frame_path
        self.window_context = dict(window_context or {})
        self._stop_event = Event()

    def cancel(self):
        self._stop_event.set()

    def run(self):
        if self._stop_event.is_set():
            return
        original_window = _get_browser_window_metadata(self.browser)
        original_frame = _get_browser_frame_path(self.browser)
        try:
            if not self.xpath:
                self.counted.emit(self.request_id, -1)
                return
            if self.window_context:
                switch_context = getattr(self.browser, "switch_to_window_context", None)
                if callable(switch_context):
                    ok = bool(
                        switch_context(
                            handle=str(self.window_context.get("handle", "") or ""),
                            window_url=str(self.window_context.get("url", "") or ""),
                            title=str(self.window_context.get("title", "") or ""),
                        )
                    )
                    if not ok:
                        message = str(getattr(self.browser, "last_error", "") or "window switch failed")
                        try:
                            setattr(self.browser, "last_error", message)
                        except Exception:
                            pass
                        self.counted.emit(self.request_id, -1)
                        return
            count = self.browser.count_elements(self.xpath, self.frame_path)
            if not self._stop_event.is_set():
                self.counted.emit(self.request_id, count)
        except Exception as e:
            if not self._stop_event.is_set():
                self.failed.emit(self.request_id, str(e))
        finally:
            _restore_browser_context(
                self.browser,
                window_handle=str(original_window.get("handle", "") or ""),
                frame_path=original_frame,
            )
            self._stop_event.clear()
