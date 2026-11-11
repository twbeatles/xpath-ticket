# -*- coding: utf-8 -*-
"""XPath Explorer worker support imports."""

import logging
from threading import Event

from xpath_explorer.qt_compat import QThread, Signal
from xpath_explorer.tools.ai import XPathAIAssistant

logger = logging.getLogger('XPathExplorer')


class AIGenerateWorker(QThread):
    """AI XPath 생성 워커."""
    generated = Signal(int, object)  # request_id, XPathSuggestion
    failed = Signal(int, str)        # request_id, error

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
