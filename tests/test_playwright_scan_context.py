from typing import Any, cast

from xpath_explorer.browser.playwright import PlaywrightManager


class _FakeFrame:
    def __init__(self, name: str, rows=None, children=None):
        self.name = name
        self.url = f"https://frames.example/{name or 'main'}"
        self.child_frames = list(children or [])
        self.rows = list(rows or [])
        self.calls = []

    def eval_on_selector_all(self, selector, script, max_count):
        self.calls.append((selector, script, max_count))
        return self.rows[:max_count]


class _FakePage:
    def __init__(self, title: str, url: str, main_frame: _FakeFrame, closed: bool = False):
        self._title = title
        self.url = url
        self.main_frame = main_frame
        self._closed = closed

    def title(self):
        return self._title

    def is_closed(self):
        return self._closed

    def evaluate(self, _script):
        if self._closed:
            raise RuntimeError("page closed")
        return True


class _FakeContext:
    def __init__(self, pages):
        self.pages = list(pages)


def _row(tag="button", text="Book"):
    return {
        "xpath": "//button",
        "css_selector": "button",
        "tag": tag,
        "text": text,
        "element_id": "",
        "element_name": "",
        "element_class": "",
        "is_visible": True,
        "is_enabled": True,
    }


def test_playwright_scan_current_window_frames_fills_frame_and_window_metadata():
    child = _FakeFrame("child", rows=[_row(text="Child")])
    main = _FakeFrame("", rows=[_row(text="Main")], children=[child])
    page = _FakePage("Root", "https://root.example", main)
    manager = PlaywrightManager()
    manager._is_initialized = True
    cast(Any, manager)._page = page
    cast(Any, manager)._context = _FakeContext([page])
    cast(Any, manager)._current_frame = main

    elements = manager.scan_elements("button", scope="current_window_frames")

    assert [element.frame_path for element in elements] == ["main", "child"]
    assert {element.window_title for element in elements} == {"Root"}
    assert {element.window_url for element in elements} == {"https://root.example"}


def test_playwright_scan_all_pages_includes_popup_frames():
    root = _FakePage("Root", "https://root.example", _FakeFrame("", rows=[_row(text="Root")]))
    popup = _FakePage("Popup", "https://popup.example", _FakeFrame("", rows=[_row(text="Popup")]))
    manager = PlaywrightManager()
    manager._is_initialized = True
    cast(Any, manager)._page = root
    cast(Any, manager)._context = _FakeContext([root, popup])
    cast(Any, manager)._current_frame = root.main_frame

    elements = manager.scan_elements("button", scope="all_pages_frames")

    assert [element.window_title for element in elements] == ["Root", "Popup"]
    assert [element.window_handle for element in elements] == ["pw-page-1", "pw-page-2"]
    assert [element.source_engine for element in elements] == ["playwright", "playwright"]

