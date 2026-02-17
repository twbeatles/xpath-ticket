from PyQt6.QtCore import QCoreApplication

from xpath_config import XPathItem
from xpath_workers import BatchTestWorker


class FakeBrowser:
    def validate_xpath(self, xpath: str):
        return {"found": True, "msg": "", "xpath": xpath}


def _ensure_qt_app():
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    return app


def test_batch_worker_cancel_stops_before_processing():
    _ensure_qt_app()
    items = [
        XPathItem(name="a", xpath="//a", category="common"),
        XPathItem(name="b", xpath="//b", category="common"),
    ]

    out = {}
    worker = BatchTestWorker(FakeBrowser(), items)
    worker.completed.connect(lambda results, cancelled: out.update(results=results, cancelled=cancelled))

    worker.cancel()
    worker.run()

    assert out["cancelled"] is True
    assert out["results"] == []
