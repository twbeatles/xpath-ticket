# -*- coding: utf-8 -*-
"""
XPath Explorer Workers
- Thread-safe implementation with Event
- Improved exception handling
"""

import time
import logging
from typing import List, Optional, Any, Dict
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


class BatchScenarioWorker(QThread):
    """JSON 기반 배치 시나리오 실행 워커."""

    progress = pyqtSignal(int, str)
    step_completed = pyqtSignal(dict)
    completed = pyqtSignal(list, bool, str)  # results, cancelled, scenario_name

    def __init__(self, browser: BrowserManager, items: List[XPathItem], scenario: Dict[str, Any]):
        super().__init__()
        self.browser = browser
        self.items = list(items or [])
        self.scenario = scenario if isinstance(scenario, dict) else {}
        self._stop_event = Event()
        self._item_map = {item.name: item for item in self.items}

    def cancel(self):
        self._stop_event.set()

    @staticmethod
    def _to_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @classmethod
    def _normalize_steps(cls, raw_steps: Any) -> List[Dict[str, Any]]:
        if not isinstance(raw_steps, list):
            return []

        steps: List[Dict[str, Any]] = []
        for idx, raw in enumerate(raw_steps, start=1):
            if not isinstance(raw, dict):
                continue
            action = str(raw.get("action") or "").strip().lower()
            if not action:
                continue

            wait_seconds = cls._to_float(
                raw.get("seconds", raw.get("wait_seconds", raw.get("wait", 0.0))),
                default=0.0,
            )
            step = {
                "index": idx,
                "name": str(raw.get("name") or f"step_{idx}"),
                "action": action,
                "item_name": str(raw.get("item") or raw.get("item_name") or ""),
                "xpath": str(raw.get("xpath") or ""),
                "frame_path": str(raw.get("frame_path") or ""),
                "wait_seconds": max(0.0, wait_seconds),
            }
            steps.append(step)
        return steps

    def _wait_with_cancel(self, seconds: float):
        remaining = max(0.0, float(seconds))
        while remaining > 0 and not self._stop_event.is_set():
            tick = min(0.1, remaining)
            self._stop_event.wait(timeout=tick)
            remaining -= tick

    def _run_validate(self, xpath: str, preferred_frame: str, session: Any) -> Dict[str, Any]:
        try:
            try:
                result = self.browser.validate_xpath(
                    xpath,
                    preferred_frame=preferred_frame or None,
                    session=session,
                )
            except TypeError:
                result = self.browser.validate_xpath(xpath)
        except Exception as e:
            return {
                "success": False,
                "msg": str(e),
                "frame_path": preferred_frame or "",
                "count": 0,
            }

        success = bool(result.get("found", False))
        msg = str(result.get("msg", "")) or ("Found" if success else "Not found")
        return {
            "success": success,
            "msg": msg,
            "frame_path": str(result.get("frame_path", "") or preferred_frame or ""),
            "count": int(result.get("count", 1 if success else 0) or 0),
        }

    def run(self):
        scenario_name = str(self.scenario.get("name") or "시나리오")
        steps = self._normalize_steps(self.scenario.get("steps"))
        results: List[Dict[str, Any]] = []
        cancelled = False

        if not self.browser.is_alive():
            self.completed.emit(results, False, scenario_name)
            return
        if not steps:
            self.completed.emit(results, False, scenario_name)
            return

        begin_session = getattr(self.browser, "begin_validation_session", None)
        end_session = getattr(self.browser, "end_validation_session", None)
        session = begin_session() if callable(begin_session) else None

        total = len(steps)
        try:
            for idx, step in enumerate(steps, start=1):
                if self._stop_event.is_set():
                    cancelled = True
                    break

                self.progress.emit(
                    int(((idx - 1) / max(1, total)) * 100),
                    f"시나리오 실행 중: {step['name']} ({idx}/{total})",
                )

                started = time.perf_counter()
                action = step["action"]
                item_name = step.get("item_name", "")
                xpath = step.get("xpath", "")
                frame_path = step.get("frame_path", "")
                target = ""
                success = False
                msg = ""
                count = 0

                if action in ("wait", "sleep"):
                    wait_seconds = float(step.get("wait_seconds", 0.0))
                    target = f"{wait_seconds:.2f}s"
                    self._wait_with_cancel(wait_seconds)
                    success = not self._stop_event.is_set()
                    msg = f"waited {wait_seconds:.2f}s"
                elif action in ("validate_item", "item"):
                    item = self._item_map.get(item_name)
                    if item is None:
                        target = item_name
                        success = False
                        msg = f"item not found: {item_name}"
                    else:
                        xpath = item.xpath
                        if not frame_path:
                            frame_path = item.found_frame or ""
                        target = xpath
                        outcome = self._run_validate(xpath, frame_path, session)
                        success = bool(outcome["success"])
                        msg = str(outcome["msg"])
                        frame_path = str(outcome["frame_path"])
                        count = int(outcome["count"])
                elif action in ("validate_xpath", "xpath", "validate"):
                    if not xpath:
                        success = False
                        msg = "xpath is empty"
                    else:
                        target = xpath
                        outcome = self._run_validate(xpath, frame_path, session)
                        success = bool(outcome["success"])
                        msg = str(outcome["msg"])
                        frame_path = str(outcome["frame_path"])
                        count = int(outcome["count"])
                else:
                    success = False
                    msg = f"unsupported action: {action}"

                duration_ms = int((time.perf_counter() - started) * 1000)
                row = {
                    "step": idx,
                    "name": step["name"],
                    "action": action,
                    "item_name": item_name,
                    "xpath": xpath,
                    "target": target,
                    "frame_path": frame_path,
                    "count": count,
                    "success": success,
                    "msg": msg,
                    "duration_ms": duration_ms,
                }
                results.append(row)
                self.step_completed.emit(row)

                if self._stop_event.is_set():
                    cancelled = True
                    break

            self.progress.emit(100, "시나리오 실행 완료")
            self.completed.emit(results, cancelled, scenario_name)
        finally:
            if callable(end_session):
                try:
                    end_session(session)
                except Exception:
                    pass
            self._stop_event.clear()
