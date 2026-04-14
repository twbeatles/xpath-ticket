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

class InstallChromiumWorker(QThread):
    """Playwright Chromium 설치 워커."""

    completed = pyqtSignal(bool, str)  # success, message

    def __init__(self, installer: Optional[Any] = None):
        super().__init__()
        self._installer = installer
        self._stop_event = Event()

    def cancel(self):
        self._stop_event.set()

    def run(self):
        if self._stop_event.is_set():
            self.completed.emit(False, "cancelled")
            self._stop_event.clear()
            return

        install_fn = self._installer
        if install_fn is None:
            try:
                from xpath_explorer.browser.playwright import PlaywrightManager

                install_fn = PlaywrightManager.install_chromium
            except Exception as e:
                self.completed.emit(False, f"installer unavailable: {e}")
                self._stop_event.clear()
                return

        try:
            ok = bool(install_fn())
            if self._stop_event.is_set():
                self.completed.emit(False, "cancelled")
            elif ok:
                self.completed.emit(True, "")
            else:
                self.completed.emit(False, "chromium install failed")
        except Exception as e:
            self.completed.emit(False, str(e))
        finally:
            self._stop_event.clear()
