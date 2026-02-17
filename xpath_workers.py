# -*- coding: utf-8 -*-
"""
XPath Explorer Workers
- Thread-safe implementation with Event
- Improved exception handling
"""

import time
import logging
from typing import List, Optional, Any
from threading import Event
from PyQt6.QtCore import QThread, pyqtSignal

from xpath_browser import BrowserManager
from xpath_config import XPathItem
from xpath_constants import PICKER_POLL_INTERVAL_MS, PICKER_ACTIVE_CHECK_TICKS
from xpath_ai import XPathAIAssistant
from xpath_diff import XPathDiffAnalyzer

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
                    
                    # 활성 상태 체크 (주기적)
                    if retry_count >= active_check_ticks:
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


class ValidateWorker(QThread):
    """검증 워커 (강화된 예외 처리, 스레드 안전)"""
    progress = pyqtSignal(int, str)
    validated = pyqtSignal(str, dict)
    finished = pyqtSignal(int, int)
    
    def __init__(self, browser: BrowserManager, items: List[XPathItem], handles: List[str]):
        super().__init__()
        self.browser = browser
        self.items = items
        self.handles = handles or []
        self._stop_event = Event()  # 스레드 안전한 이벤트
        
    def cancel(self):
        """스레드 취소 요청 (스레드 안전)"""
        self._stop_event.set()
        
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
                if self._stop_event.is_set():
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
                
                # Event 기반 대기 (인터럽트 가능)
                if self._stop_event.wait(timeout=0.1):
                    break
                
            self.progress.emit(100, "완료")
            self.finished.emit(found_total, total)
            
        finally:
            self._stop_event.clear()
            # 원래 윈도우로 안전하게 복귀
            if original_window is not None:
                try:
                    self.browser.switch_window(original_window)
                except Exception as e:
                    logger.debug(f"원래 윈도우 복귀 실패 (무시됨): {e}")


class LivePreviewWorker(QThread):
    """실시간 프리뷰용 요소 카운트 워커"""
    counted = pyqtSignal(int, int)  # request_id, count
    failed = pyqtSignal(int, str)   # request_id, error

    def __init__(self, browser: BrowserManager, xpath: str, request_id: int, frame_path: Optional[str] = None):
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


class AIGenerateWorker(QThread):
    """AI XPath 생성 워커"""
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


class DiffAnalyzeWorker(QThread):
    """Diff 분석 워커"""
    progress = pyqtSignal(int, str)
    completed = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, items: List[XPathItem], browser: BrowserManager, analyzer: XPathDiffAnalyzer):
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
                        current_info = {'found': False, 'msg': '요소 없음'}
                except Exception as e:
                    current_info = {'found': False, 'msg': str(e)}
                results.append(self.analyzer.compare_element(item, current_info))

            self.progress.emit(100, "완료")
            self.completed.emit(results)
        except Exception as e:
            self.failed.emit(str(e))
        finally:
            self._stop_event.clear()


class BatchTestWorker(QThread):
    """배치 테스트 워커"""
    progress = pyqtSignal(int, str)
    item_tested = pyqtSignal(str, bool, str, str)  # name, success, xpath, msg
    completed = pyqtSignal(list, bool)  # results, cancelled

    def __init__(self, browser: BrowserManager, items: List[XPathItem]):
        super().__init__()
        self.browser = browser
        self.items = items
        self._stop_event = Event()

    def cancel(self):
        self._stop_event.set()

    def run(self):
        total = len(self.items)
        results = []
        cancelled = False

        if total == 0:
            self.completed.emit(results, cancelled)
            return

        for i, item in enumerate(self.items):
            if self._stop_event.is_set():
                cancelled = True
                break

            self.progress.emit(int((i / total) * 100), f"테스트 중: {item.name} ({i+1}/{total})")

            try:
                result = self.browser.validate_xpath(item.xpath)
                success = result.get('found', False)
                msg = result.get('msg', '')
            except Exception as e:
                success = False
                msg = str(e)

            row = {
                'name': item.name,
                'success': success,
                'xpath': item.xpath,
                'msg': msg
            }
            results.append(row)
            self.item_tested.emit(item.name, success, item.xpath, msg)

            if self._stop_event.wait(timeout=0.01):
                cancelled = True
                break

        self.completed.emit(results, cancelled)
        self._stop_event.clear()
