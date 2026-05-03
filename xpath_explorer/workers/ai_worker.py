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
    _get_browser_window_metadata,
    _switch_browser_to_item_window,
    _window_context_from_item,
)

class AIGenerateWorker(QThread):
    """AI XPath 생성 워커."""
    generated = pyqtSignal(int, object)  # request_id, XPathSuggestion
    failed = pyqtSignal(int, str)        # request_id, error

    def __init__(self, assistant: XPathAIAssistant, description: str, request_id: int):
        super().__init__()
        self.assistant = assistant
        self.description = description
        self.request_id = request_id
        self._stop_event = Event()

    def cancel(self):
        self._stop_event.set()

    def run(self):
        if self._stop_event.is_set():
            return
        try:
            result = self.assistant.generate_xpath_from_description(self.description)
            if not self._stop_event.is_set():
                self.generated.emit(self.request_id, result)
        except Exception as e:
            if not self._stop_event.is_set():
                self.failed.emit(self.request_id, str(e))
        finally:
            self._stop_event.clear()
