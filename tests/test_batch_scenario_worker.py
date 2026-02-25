from PyQt6.QtCore import QCoreApplication

from xpath_config import XPathItem
from xpath_workers import BatchScenarioWorker


class _FakeBrowser:
    def __init__(self):
        self.begin_calls = 0
        self.end_calls = 0
        self.validate_calls = []

    def is_alive(self):
        return True

    def begin_validation_session(self):
        self.begin_calls += 1
        return {"frames": ["main"], "hints": {}, "misses": set()}

    def end_validation_session(self, _session):
        self.end_calls += 1

    def validate_xpath(self, xpath, preferred_frame=None, session=None):
        self.validate_calls.append((xpath, preferred_frame, session))
        if xpath == "//ok":
            return {"found": True, "msg": "", "frame_path": preferred_frame or "main", "count": 1}
        return {"found": False, "msg": "not found", "frame_path": preferred_frame or "main", "count": 0}


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
