# -*- coding: utf-8 -*-
"""
XPath Explorer Workers
- Thread-safe implementation with Event
- Improved exception handling
"""

import time
import logging
from typing import List, Optional
from threading import Event
from PyQt6.QtCore import QThread, pyqtSignal

from xpath_browser import BrowserManager
from xpath_config import XPathItem

logger = logging.getLogger('XPathExplorer')

class PickerWatcher(QThread):
    """요소 선택 감시 (스레드 안전)"""
    picked = pyqtSignal(dict)
    cancelled = pyqtSignal()
    
    def __init__(self, browser: BrowserManager):
        super().__init__()
        self.browser = browser
        self._stop_event = Event()  # 스레드 안전한 이벤트
        self._reinject_count = 0
        
    def stop(self):
        """스레드 중지 요청 (스레드 안전)"""
        self._stop_event.set()
        
    def run(self):
        """피커 감시 스레드 실행"""
        # 시작 전 확인
        if not self.browser.is_alive():
            self.cancelled.emit()
            return
        
        retry_count = 0
        self._reinject_count = 0
        MAX_REINJECT = 5
        
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
                    
                    # 활성 상태 체크 (1초마다)
                    if retry_count > 10:
                        if not self.browser.is_picker_active():
                            self._reinject_count += 1
                            if self._reinject_count > MAX_REINJECT:
                                logger.warning(f"피커 재주입 횟수 초과 ({MAX_REINJECT}회), 작업 취소")
                                self.cancelled.emit()
                                break
                            
                            logger.debug(f"피커 재주입 시도 ({self._reinject_count}/{MAX_REINJECT})")
                            self.browser.start_picker()
                        retry_count = 0
                        
                    retry_count += 1
                    
                    # Event 기반 대기 (인터럽트 가능)
                    if self._stop_event.wait(timeout=0.1):
                        break
                    
                except Exception as e:
                    logger.error(f"PickerWatcher 오류: {e}")
                    self.cancelled.emit()
                    break
        finally:
            self._stop_event.clear()
            self._reinject_count = 0
            logger.debug("PickerWatcher 스레드 종료")


class ValidateWorker(QThread):
    """검증 워커 (강화된 예외 처리)"""
    progress = pyqtSignal(int, str)
    validated = pyqtSignal(str, dict)
    finished = pyqtSignal(int, int)
    
    def __init__(self, browser: BrowserManager, items: List[XPathItem], handles: List[str]):
        super().__init__()
        self.browser = browser
        self.items = items
        self.handles = handles or []
        self._cancelled = False
        
    def cancel(self):
        self._cancelled = True
        
    def run(self):
        if not self.browser.is_alive():
            self.finished.emit(0, len(self.items))
            return
        
        # 원래 윈도우 핸들 안전하게 저장
        original_window: Optional[str] = None
        try:
            original_window = self.browser.driver.current_window_handle
        except Exception as e:
            logger.warning(f"현재 윈도우 핸들 가져오기 실패 (계속 진행): {e}")
            
        total = len(self.items)
        found_total = 0
        
        try:
            for i, item in enumerate(self.items):
                if self._cancelled:
                    break
                    
                self.progress.emit(int((i / total) * 100), f"검증 중: {item.name}")
                
                try:
                    result = self.browser.validate_xpath(item.xpath)
                    
                    if result.get('found', False):
                        found_total += 1
                        
                    self.validated.emit(item.name, result)
                except Exception as e:
                    logger.error(f"항목 검증 실패 ({item.name}): {e}")
                    self.validated.emit(item.name, {"found": False, "msg": str(e)})
                
                time.sleep(0.1)  # UI 응답성 확보
                
            self.progress.emit(100, "완료")
            self.finished.emit(found_total, total)
            
        finally:
            # 원래 윈도우로 안전하게 복귀
            if original_window is not None:
                try:
                    self.browser.switch_window(original_window)
                except Exception as e:
                    logger.debug(f"원래 윈도우 복귀 실패 (무시됨): {e}")
