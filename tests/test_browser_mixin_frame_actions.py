from typing import Any

import xpath_explorer.mixins.browser_mixin as browser_mixin_module
from xpath_explorer.core.config import SiteConfig, XPathItem
from xpath_explorer.mixins.browser_mixin import ExplorerBrowserMixin


class _FakeLineEdit:
    def __init__(self):
        self._text = ""

    def text(self):
        return self._text

    def setText(self, value):
        self._text = value


class _FakePlainTextEdit:
    def __init__(self):
        self._text = ""

    def toPlainText(self):
        return self._text

    def setPlainText(self, value):
        self._text = value


class _FakeTextEdit:
    def __init__(self):
        self.value = ""

    def setPlainText(self, value):
        self.value = value


class _FakeLabel:
    def __init__(self):
        self.text = ""
        self.tooltip = ""
        self.style = ""

    def setText(self, value):
        self.text = value

    def setToolTip(self, value):
        self.tooltip = value

    def setStyleSheet(self, value):
        self.style = value


class _FakeComboBox:
    def __init__(self):
        self._items = []
        self._index = -1
        self._blocked = False

    def addItem(self, label, data):
        self._items.append((label, data))
        if self._index < 0:
            self._index = 0

    def clear(self):
        self._items = []
        self._index = -1

    def count(self):
        return len(self._items)

    def currentIndex(self):
        return self._index

    def setCurrentIndex(self, index):
        self._index = index

    def itemData(self, index):
        return self._items[index][1]

    def findData(self, value):
        for idx, (_label, data) in enumerate(self._items):
            if data == value:
                return idx
        return -1

    def blockSignals(self, blocked):
        self._blocked = blocked


class _FakeWorkerSignal:
    def __init__(self):
        self._slots = []

    def connect(self, slot):
        self._slots.append(slot)


class _CaptureWorker:
    instances = []

    def __init__(self, browser, xpath, request_id, frame_path=None):
        self.browser = browser
        self.xpath = xpath
        self.request_id = request_id
        self.frame_path = frame_path
        self.counted = _FakeWorkerSignal()
        self.failed = _FakeWorkerSignal()
        self.finished = _FakeWorkerSignal()
        _CaptureWorker.instances.append(self)

    def start(self):
        return None


class _FakeBrowser:
    def __init__(self):
        self.current_frame_path = ""
        self.driver = object()
        self.last_error = ""
        self.highlight_calls = []
        self.screenshot_calls = []
        self.switch_calls = []
        self.window_switch_calls = []
        self.window_context_calls = []
        self.current_window_handle = "main"
        self.current_window_title = "Main"
        self.current_window_url = "https://main.example"

    def is_alive(self):
        return True

    def switch_window(self, handle):
        self.window_switch_calls.append(handle)
        self.current_window_handle = handle
        if handle == "popup1":
            self.current_window_title = "Popup 1"
            self.current_window_url = "https://popup.example"
        else:
            self.current_window_title = "Main"
            self.current_window_url = "https://main.example"
        return True

    def switch_to_window_context(self, handle="", window_url="", title=""):
        self.window_context_calls.append((handle, window_url, title))
        target = handle or ("popup1" if title == "Popup 1" else "main")
        return self.switch_window(target)

    def get_current_window_metadata(self):
        return {
            "handle": self.current_window_handle,
            "title": self.current_window_title,
            "url": self.current_window_url,
            "is_popup": self.current_window_handle != "main",
        }

    def switch_to_frame_by_path(self, frame_path):
        self.switch_calls.append(frame_path)
        self.current_frame_path = "" if frame_path in ("", "main") else frame_path
        return True

    def get_all_frames(self, force_refresh=False):
        _ = force_refresh
        return [("f1", "Seat Frame")]

    def highlight(self, xpath, frame_path=None):
        self.highlight_calls.append((xpath, frame_path))
        return True

    def screenshot_element(self, xpath, save_path, frame_path=None):
        self.screenshot_calls.append((xpath, save_path, frame_path))
        return True


class _Harness(ExplorerBrowserMixin):
    browser: _FakeBrowser
    combo_windows: Any
    combo_frames: Any
    input_name: _FakeLineEdit
    input_xpath: _FakePlainTextEdit
    input_css: _FakeLineEdit
    input_desc: _FakeLineEdit
    txt_result: _FakeTextEdit
    lbl_live_preview: _FakeLabel
    live_preview_worker: Any

    def __init__(self):
        self.browser = _FakeBrowser()
        self.config = SiteConfig(
            name="site",
            url="",
            items=[
                XPathItem(
                    name="seat_button",
                    xpath="//button",
                    category="seat",
                    found_frame="f1",
                    found_window="popup1",
                    found_window_title="Popup 1",
                    found_window_url="https://popup.example",
                )
            ],
        )
        self.combo_windows = _FakeComboBox()
        self.combo_windows.addItem("Main", "main")
        self.combo_windows.addItem("Popup 1", "popup1")
        self.combo_frames = _FakeComboBox()
        self.combo_frames.addItem("메인 문서", "main")
        self.combo_frames.addItem("Seat Frame", "f1")
        self.input_name = _FakeLineEdit()
        self.input_xpath = _FakePlainTextEdit()
        self.input_css = _FakeLineEdit()
        self.input_desc = _FakeLineEdit()
        self.txt_result = _FakeTextEdit()
        self.lbl_live_preview = _FakeLabel()
        self.live_preview_worker = None
        self._live_preview_request_id = 0
        self._frame_selection_explicit = False
        self._window_selection_explicit = False
        self.toasts = []

    def _show_toast(self, message: str, toast_type: str = "info", duration: int = 3000):
        self.toasts.append((message, toast_type, duration))

    def _refresh_table(self, filter_cat=None, refresh_filters=False):
        return None

    def _add_to_history(self, xpath: str, css: str, tag: str, frame: str):
        return None


def test_resolve_active_frame_prefers_item_found_frame_when_not_explicit():
    harness = _Harness()
    harness.input_name.setText("seat_button")

    assert harness._resolve_active_frame_path() == "f1"


def test_explicit_main_frame_overrides_found_frame():
    harness = _Harness()
    harness.input_name.setText("seat_button")

    harness.combo_frames.setCurrentIndex(0)
    harness._on_frame_changed(0)

    assert harness._resolve_active_frame_path() == "main"
    assert harness.browser.switch_calls[-1] == "main"


def test_resolve_active_window_prefers_item_found_window_when_not_explicit():
    harness = _Harness()
    harness.input_name.setText("seat_button")

    assert harness._resolve_active_window_context() == {
        "handle": "popup1",
        "title": "Popup 1",
        "url": "https://popup.example",
    }


def test_explicit_main_window_overrides_found_window():
    harness = _Harness()
    harness.input_name.setText("seat_button")

    harness.combo_windows.setCurrentIndex(0)
    harness._on_window_changed(0)

    assert harness._resolve_active_window_context() == {"handle": "main", "title": "", "url": ""}
    assert harness.browser.window_switch_calls[-1] == "main"


def test_highlight_uses_resolved_frame_path():
    harness = _Harness()
    harness.input_name.setText("seat_button")
    harness.input_xpath.setPlainText("//button")

    harness._highlight_xpath()

    assert harness.browser.window_context_calls[-1] == ("popup1", "https://popup.example", "Popup 1")
    assert harness.browser.highlight_calls[-1] == ("//button", "f1")


def test_live_preview_worker_receives_resolved_frame_path(monkeypatch):
    _CaptureWorker.instances.clear()
    harness = _Harness()
    harness.input_name.setText("seat_button")
    harness.input_xpath.setPlainText("//button")

    monkeypatch.setattr(browser_mixin_module, "LivePreviewWorker", _CaptureWorker)

    harness._update_live_preview()

    assert _CaptureWorker.instances
    assert _CaptureWorker.instances[-1].frame_path == "f1"


def test_screenshot_uses_explicit_main_frame(monkeypatch):
    harness = _Harness()
    harness.input_name.setText("seat_button")
    harness.input_xpath.setPlainText("//button")
    harness.combo_frames.setCurrentIndex(0)
    harness._on_frame_changed(0)

    monkeypatch.setattr(
        browser_mixin_module.QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: ("capture.png", "PNG 파일 (*.png)"),
    )

    harness._screenshot_current_element()

    assert harness.browser.screenshot_calls[-1] == ("//button", "capture.png", "main")
