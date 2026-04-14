# -*- coding: utf-8 -*-
"""XPath Explorer worker support imports."""

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

from xpath_explorer.workers.worker_shared import (
    _get_browser_window_metadata,
    _switch_browser_to_item_window,
    _window_context_from_item,
)

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
