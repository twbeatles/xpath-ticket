# -*- coding: utf-8 -*-
"""XPath Explorer worker support imports."""

import logging
from threading import Event
from typing import Any, List

from xpath_explorer.analysis.diff import XPathDiffAnalyzer
from xpath_explorer.core.config import XPathItem
from xpath_explorer.qt_compat import QThread, Signal

logger = logging.getLogger("XPathExplorer")


class DiffAnalyzeWorker(QThread):
    """DOM diff 분석 워커."""

    progress = Signal(int, str)
    completed = Signal(list)
    failed = Signal(str)

    def __init__(
        self, items: List[XPathItem], browser: Any, analyzer: XPathDiffAnalyzer
    ):
        super().__init__()
        self.items = items
        self.browser = browser
        self.analyzer = analyzer
        self._stop_event = Event()

    def cancel(self):
        self._stop_event.set()

    def run(self):
        total = len(self.items)
        if total == 0:
            self.completed.emit([])
            return

        results = []
        try:
            for i, item in enumerate(self.items):
                if self._stop_event.is_set():
                    break
                self.progress.emit(int((i / total) * 100), f"분석 중: {item.name}")
                try:
                    current_info = self.browser.get_element_info(item.xpath)
                    if current_info is None:
                        current_info = {"found": False, "msg": "요소 없음"}
                except Exception as e:
                    current_info = {"found": False, "msg": str(e)}
                results.append(self.analyzer.compare_element(item, current_info))

            self.progress.emit(100, "완료")
            self.completed.emit(results)
        except Exception as e:
            self.failed.emit(str(e))
        finally:
            self._stop_event.clear()
