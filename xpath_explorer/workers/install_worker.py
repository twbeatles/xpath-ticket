# -*- coding: utf-8 -*-
"""XPath Explorer worker support imports."""

import logging
from threading import Event
from typing import Any, Optional

from xpath_explorer.qt_compat import QThread, Signal

logger = logging.getLogger("XPathExplorer")


class InstallChromiumWorker(QThread):
    """Playwright Chromium 설치 워커."""

    completed = Signal(bool, str)  # success, message

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
