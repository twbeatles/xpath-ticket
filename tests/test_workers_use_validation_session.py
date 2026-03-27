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
        return {"found": True, "msg": "", "frame_path": "main"}

    def switch_window(self, _handle):
        return True


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

