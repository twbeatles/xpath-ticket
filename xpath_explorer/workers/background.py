# -*- coding: utf-8 -*-
"""
XPath Explorer Workers
- Thread-safe implementation with Event
- Improved exception handling
"""

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


def _window_context_from_item(item: Any) -> Dict[str, str]:
    return {
        "handle": str(getattr(item, "found_window", "") or ""),
        "title": str(getattr(item, "found_window_title", "") or ""),
        "url": str(getattr(item, "found_window_url", "") or ""),
    }


def _get_browser_window_metadata(browser: Any) -> Dict[str, Any]:
    getter = getattr(browser, "get_current_window_metadata", None)
    if callable(getter):
        try:
            metadata = getter()
        except Exception:
            metadata = None
        if isinstance(metadata, dict):
            return metadata
    driver = getattr(browser, "driver", None)
    try:
        handle = str(getattr(driver, "current_window_handle", "") or "")
    except Exception:
        handle = ""
    return {
        "handle": handle,
        "title": "",
        "url": "",
        "is_popup": False,
    }


def _switch_browser_to_item_window(browser: Any, item: Any) -> tuple[bool, str]:
    context = _window_context_from_item(item)
    handle = context["handle"]
    title = context["title"]
    url = context["url"]
    if not any((handle, title, url)):
        return True, ""

    switch_context = getattr(browser, "switch_to_window_context", None)
    try:
        if callable(switch_context):
            ok = bool(switch_context(handle=handle, window_url=url, title=title))
        elif handle:
            ok = bool(browser.switch_window(handle))
        else:
            ok = True
    except Exception as e:
        return False, str(e)
    if ok:
        return True, ""
    return False, str(getattr(browser, "last_error", "") or "대상 창을 찾을 수 없습니다.")

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


class ValidateWorker(QThread):
    """XPath 전체 검증 워커"""
    progress = pyqtSignal(int, str)
    validated = pyqtSignal(str, dict)
    finished = pyqtSignal(int, int)

    def __init__(self, browser: Any, items: List[XPathItem], handles: List[str]):
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
            driver = getattr(self.browser, "driver", None)
            handle = getattr(driver, "current_window_handle", None)
            if isinstance(handle, str):
                original_window = handle
        except Exception as e:
            logger.warning(f"현재 윈도우 핸들 조회 실패 (계속 진행): {e}")

        total = len(self.items)
        found_total = 0
        begin_session = getattr(self.browser, "begin_validation_session", None)
        end_session = getattr(self.browser, "end_validation_session", None)
        session: Optional[Dict[str, Any]] = None
        if callable(begin_session):
            maybe_session = begin_session()
            if isinstance(maybe_session, dict):
                session = maybe_session

        try:
            for i, item in enumerate(self.items):
                if self._stop_event.is_set():
                    break

                self.progress.emit(int((i / total) * 100), f"검증 중: {item.name}")

                try:
                    ok, error_msg = _switch_browser_to_item_window(self.browser, item)
                    if not ok:
                        self.validated.emit(
                            item.name,
                            {
                                'found': False,
                                'msg': error_msg,
                                'frame_path': getattr(item, 'found_frame', '') or '',
                                'window_handle': getattr(item, 'found_window', '') or '',
                                'window_title': getattr(item, 'found_window_title', '') or '',
                                'window_url': getattr(item, 'found_window_url', '') or '',
                            },
                        )
                        continue
                    try:
                        result = cast(
                            Dict[str, Any],
                            self.browser.validate_xpath(
                                item.xpath,
                                preferred_frame=item.found_frame or None,
                                session=session,
                            ),
                        )
                    except TypeError:
                        # 구 시그니처(validate_xpath(xpath)) 호환
                        result = cast(Dict[str, Any], self.browser.validate_xpath(item.xpath))
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
    """실시간 미리보기용 요소 카운트 워커."""
    counted = pyqtSignal(int, int)  # request_id, count
    failed = pyqtSignal(int, str)   # request_id, error

    def __init__(self, browser: Any, xpath: str, request_id: int, frame_path: Optional[str] = None):
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
    """AI XPath 생성 워커."""
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
    """DOM diff 분석 워커."""
    progress = pyqtSignal(int, str)
    completed = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, items: List[XPathItem], browser: Any, analyzer: XPathDiffAnalyzer):
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

    def __init__(self, browser: Any, items: List[XPathItem]):
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
        session: Optional[Dict[str, Any]] = None
        if callable(begin_session):
            maybe_session = begin_session()
            if isinstance(maybe_session, dict):
                session = maybe_session

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
                    ok, error_msg = _switch_browser_to_item_window(self.browser, item)
                    if not ok:
                        success = False
                        msg = error_msg
                    else:
                        with perf_span("worker.batch_validate_loop"):
                            try:
                                result = cast(
                                    Dict[str, Any],
                                    self.browser.validate_xpath(
                                        item.xpath,
                                        preferred_frame=item.found_frame or None,
                                        session=session,
                                    ),
                                )
                            except TypeError:
                                # 구 시그니처(validate_xpath(xpath)) 호환
                                result = cast(Dict[str, Any], self.browser.validate_xpath(item.xpath))
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
                    'window_handle': str(_get_browser_window_metadata(self.browser).get('handle', '') or ''),
                    'window_title': str(_get_browser_window_metadata(self.browser).get('title', '') or ''),
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
    failed = pyqtSignal(str)

    def __init__(self, browser: Any, items: List[XPathItem], scenario: Dict[str, Any]):
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

    @staticmethod
    def _to_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
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
                "title": str(raw.get("title") or ""),
                "wait_seconds": max(0.0, wait_seconds),
                "retries": max(0, cls._to_int(raw.get("retries", 0), default=0)),
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

    def _run_validate_with_retry(
        self,
        xpath: str,
        preferred_frame: str,
        session: Any,
        retries: int,
    ) -> Dict[str, Any]:
        max_attempts = max(1, int(retries) + 1)
        current_frame = preferred_frame or ""
        last_outcome = {
            "success": False,
            "msg": "validation not executed",
            "frame_path": current_frame,
            "count": 0,
        }
        attempt = 1

        for attempt in range(1, max_attempts + 1):
            if self._stop_event.is_set():
                last_outcome = {
                    "success": False,
                    "msg": "cancelled",
                    "frame_path": current_frame,
                    "count": 0,
                }
                break

            outcome = self._run_validate(xpath, current_frame, session)
            current_frame = str(outcome.get("frame_path", "") or current_frame)
            last_outcome = {
                "success": bool(outcome.get("success")),
                "msg": str(outcome.get("msg", "")),
                "frame_path": current_frame,
                "count": int(outcome.get("count", 0) or 0),
            }
            if last_outcome["success"]:
                break

        last_outcome["attempt"] = attempt
        last_outcome["max_attempts"] = max_attempts
        last_outcome["retry_count"] = max(0, attempt - 1)
        return last_outcome

    def _run_window_action(self, action: str, title: str, timeout_seconds: float) -> Dict[str, Any]:
        if action == "wait_for_popup":
            wait_for_popup = getattr(self.browser, "wait_for_popup", None)
            if not callable(wait_for_popup):
                return {"success": False, "msg": "wait_for_popup not supported"}
            popup = wait_for_popup(timeout_seconds=timeout_seconds, title=title)
            if isinstance(popup, dict):
                return {
                    "success": True,
                    "msg": "popup detected",
                    "window_handle": str(popup.get("handle", "") or ""),
                    "window_title": str(popup.get("title", "") or ""),
                }
            return {"success": False, "msg": str(getattr(self.browser, "last_error", "") or "popup not found")}

        if action == "switch_latest_popup":
            switch_latest_popup = getattr(self.browser, "switch_to_latest_popup", None)
            if not callable(switch_latest_popup):
                return {"success": False, "msg": "switch_to_latest_popup not supported"}
            ok = bool(switch_latest_popup())
            return {"success": ok, "msg": "" if ok else str(getattr(self.browser, "last_error", "") or "popup switch failed")}

        if action == "switch_window_by_title":
            switch_window_by_title = getattr(self.browser, "switch_to_window_by_title", None)
            if not callable(switch_window_by_title):
                return {"success": False, "msg": "switch_to_window_by_title not supported"}
            if not title:
                return {"success": False, "msg": "title is required"}
            ok = bool(switch_window_by_title(title))
            return {"success": ok, "msg": "" if ok else str(getattr(self.browser, "last_error", "") or "window switch failed")}

        if action == "switch_root_window":
            switch_root_window = getattr(self.browser, "switch_to_root_window", None)
            if not callable(switch_root_window):
                return {"success": False, "msg": "switch_to_root_window not supported"}
            ok = bool(switch_root_window())
            return {"success": ok, "msg": "" if ok else str(getattr(self.browser, "last_error", "") or "root window switch failed")}

        return {"success": False, "msg": f"unsupported action: {action}"}

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
        session: Optional[Dict[str, Any]] = None
        total = len(steps)
        try:
            if callable(begin_session):
                maybe_session = begin_session()
                if isinstance(maybe_session, dict):
                    session = maybe_session
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
                title = step.get("title", "")
                target = ""
                success = False
                msg = ""
                count = 0
                retries = max(0, self._to_int(step.get("retries", 0), default=0))
                attempt = 1
                max_attempts = 1
                retry_count = 0
                outcome: Dict[str, Any] = {}

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
                        ok, error_msg = _switch_browser_to_item_window(self.browser, item)
                        xpath = item.xpath
                        if not frame_path:
                            frame_path = item.found_frame or ""
                        target = xpath
                        if not ok:
                            success = False
                            msg = error_msg
                        else:
                            outcome = self._run_validate_with_retry(xpath, frame_path, session, retries=retries)
                            success = bool(outcome["success"])
                            msg = str(outcome["msg"])
                            frame_path = str(outcome["frame_path"])
                            count = int(outcome["count"])
                            attempt = int(outcome["attempt"])
                            max_attempts = int(outcome["max_attempts"])
                            retry_count = int(outcome["retry_count"])
                elif action in ("validate_xpath", "xpath", "validate"):
                    if not xpath:
                        success = False
                        msg = "xpath is empty"
                    else:
                        target = xpath
                        outcome = self._run_validate_with_retry(xpath, frame_path, session, retries=retries)
                        success = bool(outcome["success"])
                        msg = str(outcome["msg"])
                        frame_path = str(outcome["frame_path"])
                        count = int(outcome["count"])
                        attempt = int(outcome["attempt"])
                        max_attempts = int(outcome["max_attempts"])
                        retry_count = int(outcome["retry_count"])
                elif action in ("wait_for_popup", "switch_latest_popup", "switch_window_by_title", "switch_root_window"):
                    target = title or action
                    outcome = self._run_window_action(
                        action,
                        str(title or ""),
                        float(step.get("wait_seconds", 0.0) or 0.0),
                    )
                    success = bool(outcome.get("success"))
                    msg = str(outcome.get("msg", ""))
                else:
                    success = False
                    msg = f"unsupported action: {action}"

                duration_ms = int((time.perf_counter() - started) * 1000)
                window_meta = _get_browser_window_metadata(self.browser)
                row_window_handle = str(outcome.get("window_handle", "") or window_meta.get("handle", "") or "")
                row_window_title = str(outcome.get("window_title", "") or window_meta.get("title", "") or "")
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
                    "attempt": attempt,
                    "max_attempts": max_attempts,
                    "retry_count": retry_count,
                    "window_handle": row_window_handle,
                    "window_title": row_window_title,
                }
                results.append(row)
                self.step_completed.emit(row)

                if self._stop_event.is_set():
                    cancelled = True
                    break

            self.progress.emit(100, "시나리오 실행 완료")
            self.completed.emit(results, cancelled, scenario_name)
        except Exception as e:
            logger.error(f"시나리오 워커 실행 실패: {e}")
            self.failed.emit(str(e))
        finally:
            if callable(end_session):
                try:
                    end_session(session)
                except Exception:
                    pass
            self._stop_event.clear()


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
