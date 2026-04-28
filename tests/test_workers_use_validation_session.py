from PyQt6.QtCore import QCoreApplication

import pytest

from xpath_explorer.core.config import XPathItem
from xpath_explorer.workers.background import BatchTestWorker, ValidateWorker

pytestmark = pytest.mark.qt


def _ensure_qt_app():
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    return app


class _SessionBrowser:
    def __init__(self):
        self.begin_calls = 0
        self.end_calls = 0
        self.validate_sessions = []
        self.preferred_frames = []
        self.switch_context_calls = []
        self.frame_switch_calls = []
        self.current_frame_path = "original-frame"
        self.driver = type("Driver", (), {"current_window_handle": "w1"})()

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

    def end_validation_session(self, session):
        self.end_calls += 1

    def validate_xpath(self, xpath, preferred_frame=None, session=None):
        self.validate_sessions.append(session)
        self.preferred_frames.append(preferred_frame)
        return {
            "found": True,
            "msg": "",
            "frame_path": preferred_frame or "main",
            "window_handle": "w2",
            "window_title": "Popup",
            "window_url": "https://popup.example",
            "tag": "button",
            "count": 2,
        }

    def switch_window(self, _handle):
        return True

    def switch_to_window_context(self, handle="", window_url="", title=""):
        self.switch_context_calls.append((handle, window_url, title))
        return handle != "missing"

    def switch_to_frame_by_path(self, frame_path):
        self.frame_switch_calls.append(frame_path)
        self.current_frame_path = "" if frame_path == "main" else frame_path
        return True

    def get_current_window_metadata(self):
        return {"handle": "w1", "title": "Root", "url": "https://root.example"}


def test_validate_worker_uses_single_validation_session():
    _ensure_qt_app()
    browser = _SessionBrowser()
    items = [
        XPathItem(name="a", xpath="//a", category="common"),
        XPathItem(name="b", xpath="//b", category="common", found_frame="f1"),
    ]
    worker = ValidateWorker(browser, items, handles=["w1"])
    worker.run()

    assert browser.begin_calls == 1
    assert browser.end_calls == 1
    assert len(browser.validate_sessions) == 2
    assert browser.validate_sessions[0] is browser.validate_sessions[1]
    assert browser.preferred_frames == [None, "f1"]


def test_batch_worker_uses_single_validation_session():
    _ensure_qt_app()
    browser = _SessionBrowser()
    items = [
        XPathItem(name="a", xpath="//a", category="common"),
        XPathItem(name="b", xpath="//b", category="common", found_frame="f1"),
    ]
    worker = BatchTestWorker(browser, items)
    worker.run()

    assert browser.begin_calls == 1
    assert browser.end_calls == 1
    assert len(browser.validate_sessions) == 2
    assert browser.validate_sessions[0] is browser.validate_sessions[1]
    assert browser.preferred_frames == [None, "f1"]
    assert browser.frame_switch_calls[-1] == "original-frame"


def test_batch_worker_emits_full_result_metadata():
    _ensure_qt_app()
    browser = _SessionBrowser()
    items = [XPathItem(name="a", xpath="//a", category="common", found_frame="f1")]
    worker = BatchTestWorker(browser, items)
    rows = []
    worker.item_validated.connect(lambda name, result: rows.append((name, result)))

    worker.run()

    assert rows[0][0] == "a"
    result = rows[0][1]
    assert result["frame_path"] == "f1"
    assert result["window_handle"] == "w2"
    assert result["window_title"] == "Popup"
    assert result["window_url"] == "https://popup.example"
    assert result["tag"] == "button"
    assert result["count"] == 2
    assert result["error_type"] == ""


def test_validate_worker_uses_item_window_metadata_and_reports_switch_failures():
    _ensure_qt_app()
    browser = _SessionBrowser()
    items = [
        XPathItem(
            name="popup_ok",
            xpath="//a",
            category="common",
            found_window="w2",
            found_window_title="Popup",
            found_window_url="https://popup.example",
        ),
        XPathItem(
            name="popup_missing",
            xpath="//b",
            category="common",
            found_window="missing",
            found_window_title="Missing Popup",
            found_window_url="https://missing.example",
        ),
    ]
    worker = ValidateWorker(browser, items, handles=["w1", "w2"])
    validated = {}
    worker.validated.connect(lambda name, result: validated.setdefault(name, result))

    worker.run()

    assert browser.switch_context_calls == [
        ("w2", "https://popup.example", "Popup"),
        ("missing", "https://missing.example", "Missing Popup"),
    ]
    assert validated["popup_ok"]["found"] is True
    assert validated["popup_missing"]["found"] is False
    assert validated["popup_missing"]["window_handle"] == "missing"
    assert validated["popup_missing"]["window_title"] == "Missing Popup"
    assert validated["popup_missing"]["window_url"] == "https://missing.example"

