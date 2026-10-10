from PyQt6.QtCore import QCoreApplication

import pytest

from xpath_explorer.core.config import XPathItem
from xpath_explorer.workers.background import BatchScenarioWorker

pytestmark = pytest.mark.qt


class _FakeBrowser:
    def __init__(self):
        self.begin_calls = 0
        self.end_calls = 0
        self.validate_calls = []
        self._flaky_calls = 0
        self.current_handle = "root"
        self.current_title = "Root"
        self.current_frame_path = "original-frame"
        self.window_action_calls = []
        self.frame_switch_calls = []

    def is_alive(self):
        return True

    def begin_validation_session(self):
        self.begin_calls += 1
        return {
            "frames": ["main"],
            "hints": {},
            "misses": {},
            "frame_signature": "main",
        }

    def end_validation_session(self, _session):
        self.end_calls += 1

    def validate_xpath(self, xpath, preferred_frame=None, session=None):
        self.validate_calls.append((xpath, preferred_frame, session))
        if xpath == "//ok":
            return {"found": True, "msg": "", "frame_path": preferred_frame or "main", "count": 1}
        if xpath == "//flaky":
            self._flaky_calls += 1
            if self._flaky_calls >= 2:
                return {"found": True, "msg": "recovered", "frame_path": preferred_frame or "main", "count": 1}
            return {"found": False, "msg": "temporary failure", "frame_path": preferred_frame or "main", "count": 0}
        return {"found": False, "msg": "not found", "frame_path": preferred_frame or "main", "count": 0}

    def get_current_window_metadata(self):
        return {
            "handle": self.current_handle,
            "title": self.current_title,
            "url": f"https://{self.current_handle}.example",
            "is_popup": self.current_handle != "root",
        }

    def wait_for_popup(self, timeout_seconds=0.0, title=""):
        self.window_action_calls.append(("wait_for_popup", timeout_seconds, title))
        if title and title != "Popup":
            return None
        return {"handle": "popup", "title": "Popup", "url": "https://popup.example"}

    def switch_to_latest_popup(self):
        self.window_action_calls.append(("switch_to_latest_popup",))
        self.current_handle = "popup"
        self.current_title = "Popup"
        return True

    def switch_to_window_by_title(self, title):
        self.window_action_calls.append(("switch_to_window_by_title", title))
        if title != "Popup":
            return False
        self.current_handle = "popup"
        self.current_title = "Popup"
        return True

    def switch_to_root_window(self):
        self.window_action_calls.append(("switch_to_root_window",))
        self.current_handle = "root"
        self.current_title = "Root"
        return True

    def switch_to_window_context(self, handle="", window_url="", title=""):
        self.window_action_calls.append(("switch_to_window_context", handle, window_url, title))
        if handle:
            self.current_handle = handle
            self.current_title = "Root" if handle == "root" else "Popup"
        return True

    def switch_to_frame_by_path(self, frame_path):
        self.frame_switch_calls.append(frame_path)
        self.current_frame_path = "" if frame_path == "main" else frame_path
        return True


class _BrokenSessionBrowser(_FakeBrowser):
    def begin_validation_session(self):
        raise RuntimeError("session exploded")


def _ensure_qt_app():
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    return app


def test_batch_scenario_worker_runs_steps_and_reports_results():
    _ensure_qt_app()
    browser = _FakeBrowser()
    items = [
        XPathItem(name="login_id", xpath="//ok", category="login"),
    ]
    scenario = {
        "name": "smoke",
        "steps": [
            {"name": "item check", "action": "validate_item", "item": "login_id"},
            {"name": "wait", "action": "wait", "seconds": 0.01},
            {"name": "xpath check", "action": "validate_xpath", "xpath": "//missing"},
        ],
    }

    completed = {}
    rows = []
    worker = BatchScenarioWorker(browser, items, scenario)
    worker.step_completed.connect(lambda row: rows.append(row))
    worker.completed.connect(
        lambda results, cancelled, scenario_name: completed.update(
            results=results,
            cancelled=cancelled,
            scenario_name=scenario_name,
        )
    )

    worker.run()

    assert completed["scenario_name"] == "smoke"
    assert completed["cancelled"] is False
    assert len(completed["results"]) == 3
    assert len(rows) == 3

    assert completed["results"][0]["action"] == "validate_item"
    assert completed["results"][0]["success"] is True
    assert completed["results"][1]["action"] == "wait"
    assert completed["results"][1]["success"] is True
    assert completed["results"][2]["action"] == "validate_xpath"
    assert completed["results"][2]["success"] is False

    assert browser.begin_calls == 1
    assert browser.end_calls == 1
    assert len(browser.validate_calls) == 2


def test_batch_scenario_worker_cancel_before_run_marks_cancelled():
    _ensure_qt_app()
    browser = _FakeBrowser()
    items = [XPathItem(name="login_id", xpath="//ok", category="login")]
    scenario = {
        "name": "cancelled",
        "steps": [
            {"name": "wait", "action": "wait", "seconds": 0.2},
            {"name": "item check", "action": "validate_item", "item": "login_id"},
        ],
    }

    completed = {}
    worker = BatchScenarioWorker(browser, items, scenario)
    worker.completed.connect(
        lambda results, cancelled, scenario_name: completed.update(
            results=results,
            cancelled=cancelled,
            scenario_name=scenario_name,
        )
    )

    worker.cancel()
    worker.run()

    assert completed["scenario_name"] == "cancelled"
    assert completed["cancelled"] is True
    assert completed["results"] == []
    assert browser.begin_calls == 1
    assert browser.end_calls == 1
    assert browser.validate_calls == []


def test_batch_scenario_worker_retries_and_reports_attempt_metadata():
    _ensure_qt_app()
    browser = _FakeBrowser()
    scenario = {
        "name": "retry",
        "steps": [
            {"name": "flaky xpath", "action": "validate_xpath", "xpath": "//flaky", "retries": 2},
        ],
    }

    completed = {}
    worker = BatchScenarioWorker(browser, [], scenario)
    worker.completed.connect(
        lambda results, cancelled, scenario_name: completed.update(
            results=results,
            cancelled=cancelled,
            scenario_name=scenario_name,
        )
    )

    worker.run()

    assert completed["cancelled"] is False
    assert completed["scenario_name"] == "retry"
    assert len(completed["results"]) == 1
    row = completed["results"][0]
    assert row["success"] is True
    assert row["attempt"] == 2
    assert row["retry_count"] == 1
    assert row["max_attempts"] == 3
    assert len(browser.validate_calls) == 2


def test_batch_scenario_worker_emits_failed_signal_for_unhandled_error():
    _ensure_qt_app()
    browser = _BrokenSessionBrowser()
    scenario = {
        "name": "failed",
        "steps": [
            {"name": "item check", "action": "validate_xpath", "xpath": "//ok"},
        ],
    }

    failed_messages = []
    completed = []
    worker = BatchScenarioWorker(browser, [], scenario)
    worker.failed.connect(lambda message: failed_messages.append(message))
    worker.completed.connect(lambda *_args: completed.append(True))

    worker.run()

    assert completed == []
    assert failed_messages
    assert "session exploded" in failed_messages[0]


def test_batch_scenario_worker_supports_popup_and_window_switch_actions():
    _ensure_qt_app()
    browser = _FakeBrowser()
    scenario = {
        "name": "popup-flow",
        "steps": [
            {"name": "detect popup", "action": "wait_for_popup", "seconds": 0.5, "title": "Popup"},
            {"name": "switch popup", "action": "switch_latest_popup"},
            {"name": "switch by title", "action": "switch_window_by_title", "title": "Popup"},
            {"name": "back root", "action": "switch_root_window"},
        ],
    }

    completed = {}
    worker = BatchScenarioWorker(browser, [], scenario)
    worker.completed.connect(
        lambda results, cancelled, scenario_name: completed.update(
            results=results,
            cancelled=cancelled,
            scenario_name=scenario_name,
        )
    )

    worker.run()

    assert completed["cancelled"] is False
    assert completed["scenario_name"] == "popup-flow"
    assert [row["action"] for row in completed["results"]] == [
        "wait_for_popup",
        "switch_latest_popup",
        "switch_window_by_title",
        "switch_root_window",
    ]
    assert completed["results"][0]["success"] is True
    assert completed["results"][0]["window_handle"] == "popup"
    assert completed["results"][0]["window_title"] == "Popup"
    assert completed["results"][1]["window_title"] == "Popup"
    assert completed["results"][2]["window_title"] == "Popup"
    assert completed["results"][3]["window_handle"] == "root"
    assert completed["results"][3]["window_title"] == "Root"


def test_batch_scenario_worker_restores_original_context_by_default():
    _ensure_qt_app()
    browser = _FakeBrowser()
    scenario = {
        "name": "restore",
        "steps": [
            {"name": "switch popup", "action": "switch_latest_popup"},
        ],
    }

    completed = {}
    worker = BatchScenarioWorker(browser, [], scenario)
    worker.completed.connect(
        lambda results, cancelled, scenario_name: completed.update(
            results=results,
            cancelled=cancelled,
            scenario_name=scenario_name,
            final_handle=browser.current_handle,
            final_frame=browser.current_frame_path,
        )
    )

    worker.run()

    assert completed["results"][0]["window_handle"] == "popup"
    assert completed["final_handle"] == "root"
    assert completed["final_frame"] == "original-frame"


def test_batch_scenario_worker_leave_context_true_keeps_last_context():
    _ensure_qt_app()
    browser = _FakeBrowser()
    scenario = {
        "name": "leave",
        "leave_context": True,
        "steps": [
            {"name": "switch popup", "action": "switch_latest_popup"},
        ],
    }

    completed = {}
    worker = BatchScenarioWorker(browser, [], scenario)
    worker.completed.connect(
        lambda results, cancelled, scenario_name: completed.update(
            results=results,
            cancelled=cancelled,
            scenario_name=scenario_name,
            final_handle=browser.current_handle,
            final_frame=browser.current_frame_path,
        )
    )

    worker.run()

    assert completed["results"][0]["window_handle"] == "popup"
    assert completed["final_handle"] == "popup"
    assert completed["final_frame"] == "original-frame"


def test_batch_scenario_worker_clamps_wait_seconds():
    from xpath_explorer.core.constants import SCENARIO_MAX_WAIT_SECONDS

    steps = BatchScenarioWorker._normalize_steps(
        [{"action": "wait", "seconds": 99999, "name": "long"}]
    )
    assert steps[0]["wait_seconds"] == SCENARIO_MAX_WAIT_SECONDS


def test_batch_scenario_worker_clamps_retries():
    from xpath_explorer.core.constants import SCENARIO_MAX_RETRIES

    steps = BatchScenarioWorker._normalize_steps(
        [
            {"action": "validate_xpath", "xpath": "//a", "retries": 10**9},
            {"action": "validate_xpath", "xpath": "//b", "retries": -5},
        ]
    )
    assert steps[0]["retries"] == SCENARIO_MAX_RETRIES
    assert steps[1]["retries"] == 0


class _DeadBrowser(_FakeBrowser):
    def is_alive(self):
        return False


class _FakePlaywright:
    def __init__(self):
        self.validate_calls = []
        self.current_frame_path = ""

    def is_alive(self):
        return True

    def validate_xpath(self, xpath):
        self.validate_calls.append(xpath)
        if xpath == "//pw-ok":
            return {"found": True, "msg": "", "frame_path": "main", "count": 1,
                    "tag": "button", "window_handle": "pw-page",
                    "window_title": "PW", "window_url": "https://pw.example"}
        return {"found": False, "msg": "not found", "frame_path": "main", "count": 0}

    def get_current_window_metadata(self):
        return {"handle": "pw-page", "title": "PW",
                "url": "https://pw.example", "is_popup": False}


class _DeadPlaywright(_FakePlaywright):
    def is_alive(self):
        return False


def _run_worker(browser, items, scenario, playwright=None):
    _ensure_qt_app()
    outcome = {}
    worker = BatchScenarioWorker(browser, items, scenario, playwright=playwright)
    worker.completed.connect(
        lambda results, cancelled, name: outcome.update(
            kind="completed", results=results, cancelled=cancelled)
    )
    worker.failed.connect(lambda message: outcome.update(kind="failed", message=message))
    worker.run()
    return outcome


def test_scenario_playwright_only_runs_playwright_item_steps():
    browser = _DeadBrowser()
    playwright = _FakePlaywright()
    items = [XPathItem(name="pw_btn", xpath="//pw-ok", category="booking",
                       source_engine="playwright")]
    scenario = {
        "name": "pw-only",
        "steps": [
            {"name": "pw check", "action": "validate_item", "item": "pw_btn"},
            {"name": "pause", "action": "wait", "seconds": 0.01},
        ],
    }

    outcome = _run_worker(browser, items, scenario, playwright=playwright)

    assert outcome["kind"] == "completed"
    assert len(outcome["results"]) == 2
    assert outcome["results"][0]["success"] is True
    assert playwright.validate_calls == ["//pw-ok"]
    assert browser.validate_calls == []


def test_scenario_playwright_only_fails_fast_on_selenium_steps():
    browser = _DeadBrowser()
    playwright = _FakePlaywright()
    scenario = {
        "name": "pw-only-popup",
        "steps": [{"name": "popup", "action": "wait_for_popup", "seconds": 0.01}],
    }

    outcome = _run_worker(browser, [], scenario, playwright=playwright)

    assert outcome["kind"] == "failed"
    assert "Selenium" in outcome["message"]


def test_scenario_both_dead_fails_fast_instead_of_empty_completed():
    outcome = _run_worker(
        _DeadBrowser(), [],
        {"name": "dead", "steps": [{"name": "x", "action": "validate_xpath",
                                    "xpath": "//ok"}]},
        playwright=_DeadPlaywright(),
    )

    assert outcome["kind"] == "failed"
    assert "Selenium" in outcome["message"]


def test_scenario_playwright_item_falls_back_to_selenium():
    browser = _FakeBrowser()
    items = [XPathItem(name="pw_btn", xpath="//ok", category="booking",
                       source_engine="playwright")]
    scenario = {
        "name": "fallback",
        "steps": [{"name": "pw check", "action": "validate_item", "item": "pw_btn"}],
    }

    outcome = _run_worker(browser, items, scenario, playwright=_DeadPlaywright())

    assert outcome["kind"] == "completed"
    assert outcome["results"][0]["success"] is True
    assert browser.validate_calls
