from PyQt6.QtCore import QCoreApplication

from xpath_workers import LivePreviewWorker


class FakeBrowser:
    def __init__(self):
        self._counts = {
            "//first": 1,
            "//second": 2,
        }

    def count_elements(self, xpath, frame_path=None):
        return self._counts.get(xpath, -1)


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
