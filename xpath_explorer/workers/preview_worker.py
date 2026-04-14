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

class LivePreviewWorker(QThread):
    """실시간 미리보기용 요소 카운트 워커."""
    counted = pyqtSignal(int, int)  # request_id, count
    failed = pyqtSignal(int, str)   # request_id, error

    def __init__(self, browser: Any, xpath: str, request_id: int, frame_path: Optional[str] = None):
        super().__init__()
        self.browser = browser
        self.xpath = xpath
        self.request_id = request_id
        self.frame_path = frame_path
        self._stop_event = Event()

    def cancel(self):
        self._stop_event.set()

    def run(self):
        if self._stop_event.is_set():
            return
        try:
            if not self.xpath:
                self.counted.emit(self.request_id, -1)
                return
            count = self.browser.count_elements(self.xpath, self.frame_path)
            if not self._stop_event.is_set():
                self.counted.emit(self.request_id, count)
        except Exception as e:
            if not self._stop_event.is_set():
                self.failed.emit(self.request_id, str(e))
        finally:
            self._stop_event.clear()
