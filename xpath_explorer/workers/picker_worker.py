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

class PickerWatcher(QThread):
    """요소 선택 감시 워커 (스레드 안전)."""
    picked = pyqtSignal(dict)
    cancelled = pyqtSignal()
    
    def __init__(self, browser: Any):
        super().__init__()
        self.browser = browser
        self._stop_event = Event()
        self._reinject_count = 0
        
    def stop(self):
        """워커 종료 요청."""
        self._stop_event.set()
        
    def run(self):
        """요소 선택 결과를 주기적으로 확인한다."""
        if not self.browser.is_alive():
            self.cancelled.emit()
            return
        
        retry_count = 0
        self._reinject_count = 0
        MAX_REINJECT = 5
        poll_seconds = max(0.05, PICKER_POLL_INTERVAL_MS / 1000.0)
        active_check_ticks = max(1, PICKER_ACTIVE_CHECK_TICKS)
        
        try:
            while not self._stop_event.is_set():
                try:
                    # 선택 결과 확인
                    result = self.browser.get_picker_result()
                    
                    if result:
                        if result == "CANCELLED":
                            self.cancelled.emit()
                            break
                        elif isinstance(result, dict):
                            self.picked.emit(result)
                            break
                    
                    # 주기적으로 picker 활성 상태 확인
                    if retry_count >= active_check_ticks:
                        if not self.browser.is_picker_active():
                            self._reinject_count += 1
                            if self._reinject_count > MAX_REINJECT:
                                logger.warning(
                                    "Picker 재주입 최대 횟수 초과 (%s회), 작업 취소",
                                    MAX_REINJECT,
                                )
                                self.cancelled.emit()
                                break
                            
                            logger.debug(
                                "Picker 재주입 시도 (%s/%s)",
                                self._reinject_count,
                                MAX_REINJECT,
                            )
                            self.browser.start_picker()
                        retry_count = 0
                        
                    retry_count += 1
                    
                    # Event 기반 대기 (중단 신호 즉시 반영)
                    if self._stop_event.wait(timeout=poll_seconds):
                        break
                    
                except Exception as e:
                    logger.error(f"PickerWatcher 오류: {e}")
                    self.cancelled.emit()
                    break
        finally:
            self._stop_event.clear()
            self._reinject_count = 0
            logger.debug("PickerWatcher 스레드 종료")
