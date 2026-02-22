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
from xpath_perf import perf_span

logger = logging.getLogger('XPathExplorer')

class PickerWatcher(QThread):
    """?붿냼 ?좏깮 媛먯떆 (?ㅻ젅???덉쟾)"""
    picked = pyqtSignal(dict)
    cancelled = pyqtSignal()
    
    def __init__(self, browser: BrowserManager):
        super().__init__()
        self.browser = browser
        self._stop_event = Event()  # ?ㅻ젅???덉쟾???대깽??
        self._reinject_count = 0
        
    def stop(self):
        """?ㅻ젅??以묒? ?붿껌 (?ㅻ젅???덉쟾)"""
        self._stop_event.set()
        
    def run(self):
        """?쇱빱 媛먯떆 ?ㅻ젅???ㅽ뻾"""
        # ?쒖옉 ???뺤씤
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
                    # ?좏깮 寃곌낵 ?뺤씤
                    result = self.browser.get_picker_result()
                    
                    if result:
                        if result == "CANCELLED":
                            self.cancelled.emit()
                            break
                        elif isinstance(result, dict):
                            self.picked.emit(result)
                            break
                    
                    # ?쒖꽦 ?곹깭 泥댄겕 (二쇨린??
                    if retry_count >= active_check_ticks:
                        if not self.browser.is_picker_active():
                            self._reinject_count += 1
                            if self._reinject_count > MAX_REINJECT:
                                logger.warning(f"?쇱빱 ?ъ＜???잛닔 珥덇낵 ({MAX_REINJECT}??, ?묒뾽 痍⑥냼")
                                self.cancelled.emit()
                                break
                            
                            logger.debug(f"?쇱빱 ?ъ＜???쒕룄 ({self._reinject_count}/{MAX_REINJECT})")
                            self.browser.start_picker()
                        retry_count = 0
                        
                    retry_count += 1
                    
                    # Event 湲곕컲 ?湲?(?명꽣?쏀듃 媛??
                    if self._stop_event.wait(timeout=poll_seconds):
                        break
                    
                except Exception as e:
                    logger.error(f"PickerWatcher ?ㅻ쪟: {e}")
                    self.cancelled.emit()
                    break
        finally:
            self._stop_event.clear()
            self._reinject_count = 0
            logger.debug("PickerWatcher ?ㅻ젅??醫낅즺")


class ValidateWorker(QThread):
    """XPath 전체 검증 워커"""
    progress = pyqtSignal(int, str)
    validated = pyqtSignal(str, dict)
    finished = pyqtSignal(int, int)

    def __init__(self, browser: BrowserManager, items: List[XPathItem], handles: List[str]):
        super().__init__()
        self.browser = browser
        self.items = items
        self.handles = handles or []
        self._stop_event = Event()

    def cancel(self):
        self._stop_event.set()

    def run(self):
        if not self.browser.is_alive():
            self.finished.emit(0, len(self.items))
            return

        original_window: Optional[str] = None
        try:
            original_window = self.browser.driver.current_window_handle
        except Exception as e:
            logger.warning(f"현재 윈도우 핸들 조회 실패 (계속 진행): {e}")

        total = len(self.items)
        found_total = 0
        begin_session = getattr(self.browser, "begin_validation_session", None)
        end_session = getattr(self.browser, "end_validation_session", None)
        session = begin_session() if callable(begin_session) else None

        try:
            for i, item in enumerate(self.items):
                if self._stop_event.is_set():
                    break

                self.progress.emit(int((i / total) * 100), f"검증 중: {item.name}")

                try:
                    try:
                        result = self.browser.validate_xpath(item.xpath, session=session)
                    except TypeError:
                        # 구 시그니처(validate_xpath(xpath)) 호환
                        result = self.browser.validate_xpath(item.xpath)
                    if result.get('found', False):
                        found_total += 1
                    self.validated.emit(item.name, result)
                except Exception as e:
                    logger.error(f"항목 검증 실패 ({item.name}): {e}")
                    self.validated.emit(item.name, {'found': False, 'msg': str(e)})

                if self._stop_event.wait(timeout=0.1):
                    break

            self.progress.emit(100, '완료')
            self.finished.emit(found_total, total)

        finally:
            if callable(end_session):
                try:
                    end_session(session)
                except Exception:
                    pass
            self._stop_event.clear()
            if original_window is not None:
                try:
                    self.browser.switch_window(original_window)
                except Exception as e:
                    logger.debug(f"원래 윈도우 복귀 실패 (무시): {e}")


class LivePreviewWorker(QThread):
    """?ㅼ떆媛??꾨━酉곗슜 ?붿냼 移댁슫???뚯빱"""
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
    """AI XPath ?앹꽦 ?뚯빱"""
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
    """Diff 遺꾩꽍 ?뚯빱"""
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
                self.progress.emit(int((i / total) * 100), f"遺꾩꽍 以? {item.name}")
                try:
                    current_info = self.browser.get_element_info(item.xpath)
                    if current_info is None:
                        current_info = {'found': False, 'msg': '?붿냼 ?놁쓬'}
                except Exception as e:
                    current_info = {'found': False, 'msg': str(e)}
                results.append(self.analyzer.compare_element(item, current_info))

            self.progress.emit(100, "?꾨즺")
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
        begin_session = getattr(self.browser, "begin_validation_session", None)
        end_session = getattr(self.browser, "end_validation_session", None)
        session = begin_session() if callable(begin_session) else None

        if total == 0:
            if callable(end_session):
                try:
                    end_session(session)
                except Exception:
                    pass
            self.completed.emit(results, cancelled)
            return

        try:
            for i, item in enumerate(self.items):
                if self._stop_event.is_set():
                    cancelled = True
                    break

                self.progress.emit(int((i / total) * 100), f"테스트 중: {item.name} ({i+1}/{total})")

                try:
                    with perf_span("worker.batch_validate_loop"):
                        try:
                            result = self.browser.validate_xpath(item.xpath, session=session)
                        except TypeError:
                            # 구 시그니처(validate_xpath(xpath)) 호환
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
                    'msg': msg,
                }
                results.append(row)
                self.item_tested.emit(item.name, success, item.xpath, msg)

                if self._stop_event.wait(timeout=0.01):
                    cancelled = True
                    break
        finally:
            if callable(end_session):
                try:
                    end_session(session)
                except Exception:
                    pass
            self.completed.emit(results, cancelled)
            self._stop_event.clear()
