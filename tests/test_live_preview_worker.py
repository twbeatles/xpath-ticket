from PyQt6.QtCore import QCoreApplication

import pytest

from xpath_explorer.workers.background import LivePreviewWorker

pytestmark = pytest.mark.qt


class FakeBrowser:
    def __init__(self):
        self._counts = {
            "//first": 1,
            "//second": 2,
        }
        self.calls = []
        self.current_frame_path = "original-frame"
        self.window_context_calls = []
        self.frame_switch_calls = []
        self.last_error = ""

    def count_elements(self, xpath, frame_path=None):
        self.calls.append((xpath, frame_path))
        return self._counts.get(xpath, -1)

    def get_current_window_metadata(self):
        return {"handle": "root", "title": "Root", "url": "https://root.example"}

    def switch_to_window_context(self, handle="", window_url="", title=""):
        self.window_context_calls.append((handle, window_url, title))
        if handle == "missing":
            self.last_error = "target window missing"
            return False
        return True

    def switch_to_frame_by_path(self, frame_path):
        self.frame_switch_calls.append(frame_path)
        self.current_frame_path = "" if frame_path == "main" else frame_path
        return True


def _ensure_qt_app():
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    return app


def test_live_preview_worker_emits_request_id_and_count():
    _ensure_qt_app()
    browser = FakeBrowser()
    got = {}

    worker = LivePreviewWorker(browser, "//first", 101)
    worker.counted.connect(lambda req_id, count: got.update(req_id=req_id, count=count))
    worker.run()

    assert got["req_id"] == 101
    assert got["count"] == 1


def test_latest_request_can_ignore_stale_worker_result():
    _ensure_qt_app()
    browser = FakeBrowser()
    latest = {"request_id": 2, "count": None}

    def on_count(request_id, count):
        if request_id != latest["request_id"]:
            return
        latest["count"] = count

    # newer result arrives first
    newer = LivePreviewWorker(browser, "//second", 2)
    older = LivePreviewWorker(browser, "//first", 1)
    newer.counted.connect(on_count)
    older.counted.connect(on_count)

    newer.run()
    older.run()

    assert latest["count"] == 2


def test_live_preview_worker_passes_frame_path():
    _ensure_qt_app()
    browser = FakeBrowser()

    worker = LivePreviewWorker(browser, "//first", 303, frame_path="frame://seat")
    worker.run()

    assert browser.calls[-1] == ("//first", "frame://seat")


def test_live_preview_worker_uses_window_context_and_restores_context():
    _ensure_qt_app()
    browser = FakeBrowser()

    worker = LivePreviewWorker(
        browser,
        "//first",
        404,
        frame_path="frame://seat",
        window_context={"handle": "popup", "title": "Popup", "url": "https://popup.example"},
    )
    worker.run()

    assert browser.window_context_calls == [
        ("popup", "https://popup.example", "Popup"),
        ("root", "", ""),
    ]
    assert browser.frame_switch_calls[-1] == "original-frame"
    assert browser.calls[-1] == ("//first", "frame://seat")


def test_live_preview_worker_reports_negative_count_on_window_switch_failure():
    _ensure_qt_app()
    browser = FakeBrowser()
    got = {}

    worker = LivePreviewWorker(
        browser,
        "//first",
        505,
        window_context={"handle": "missing", "title": "Missing", "url": "https://missing.example"},
    )
    worker.counted.connect(lambda req_id, count: got.update(req_id=req_id, count=count))
    worker.run()

    assert got == {"req_id": 505, "count": -1}
    assert browser.calls == []
    assert browser.last_error == "target window missing"
