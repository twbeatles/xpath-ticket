# -*- coding: utf-8 -*-
"""
XPath Explorer Workers
"""

import time
from typing import List
from PyQt6.QtCore import QThread, pyqtSignal

from xpath_browser import BrowserManager
from xpath_config import XPathItem

class PickerWatcher(QThread):
    """요소 선택 감시"""
    picked = pyqtSignal(dict)
    cancelled = pyqtSignal()
    
    def __init__(self, browser: BrowserManager):
        super().__init__()
        self.browser = browser
        self._running = True
        
    def stop(self):
        self._running = False
        
    def run(self):
        # 시작 전 확인
        if not self.browser.is_alive():
            self.cancelled.emit()
            return
            
        retry_count = 0
        max_retries = 3
        
        while self._running:
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
                
                # 활성 상태 체크 (너무 자주는 부하 확인)
                if retry_count > 10: # 1초마다 체크
                    if not self.browser.is_picker_active():
                         # 사용자가 새로고침 등으로 스크립트가 날아간 경우 재주입
                        self.browser.start_picker()
                    retry_count = 0
                    
                retry_count += 1
                time.sleep(0.1)
                
            except Exception as e:
                # 브라우저 연결 끊김 등
                self.cancelled.emit()
                break


class ValidateWorker(QThread):
    """검증 워커"""
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
            
        original_window = ""
        try:
            original_window = self.browser.driver.current_window_handle
        except:
            pass
            
        total = len(self.items)
        found_total = 0
        
        # 1. 윈도우별 검증 필요?
        # 복잡도를 줄이기 위해, 현재 활성화된 윈도우(사용자가 선택한)에서만 검증하거나
        # 다중 윈도우라면 각 아이템 별로 저장된 found_window가 있다면 거기로 이동
        
        for i, item in enumerate(self.items):
            if self._cancelled:
                break
                
            self.progress.emit(int((i / total) * 100), f"검증 중: {item.name}")
            
            # TODO: 아이템별 윈도우 전환 지원 계획
            # if item.found_window in self.handles:
            #     self.browser.switch_window(item.found_window)
            
            result = self.browser.validate_xpath(item.xpath)
            
            if result['found']:
                found_total += 1
                
            self.validated.emit(item.name, result)
            time.sleep(0.1)  # UI 응답성 확보
            
        self.progress.emit(100, "완료")
        self.finished.emit(found_total, total)
        
        # 원래 윈도우 복귀
        if original_window:
            self.browser.switch_window(original_window)
