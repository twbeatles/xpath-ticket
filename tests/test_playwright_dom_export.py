from typing import Any, cast

from xpath_explorer.browser.playwright import PlaywrightManager


class _FakeFrame:
    def __init__(self, name: str, url: str, html: str = "", error: str = "", children=None):
        self.name = name
        self.url = url
        self._html = html
        self._error = error
        self.child_frames = list(children or [])

    def evaluate(self, _script):
        if self._error:
            raise Exception(self._error)
        return self._html


class _FakePage:
    def __init__(self, title: str, url: str, main_frame: _FakeFrame, closed: bool = False):
        self._title = title
        self.url = url
        self.main_frame = main_frame
        self._closed = closed
        self._handlers = {}

    def title(self):
        return self._title

    def is_closed(self):
        return self._closed

    def evaluate(self, _script):
        if self._closed:
            raise Exception("page closed")
        return True

    def on(self, event, handler):
        self._handlers[event] = handler


class _FakeContext:
    def __init__(self, pages):
        self.pages = list(pages)


def test_collect_dom_snapshots_collects_pages_popups_frames_and_errors():
    root_child = _FakeFrame(
        name="childA",
        url="https://root.example/child",
        html="<html><body>root-child</body></html>",
    )
    root_main = _FakeFrame(
        name="",
        url="https://root.example",
        html="<html><body>root-main</body></html>",
        children=[root_child],
    )
    popup_child_error = _FakeFrame(
        name="",
        url="https://popup.example/frame1",
        error="frame detached",
    )
    popup_main = _FakeFrame(
        name="",
        url="https://popup.example",
        html="<html><body>popup-main</body></html>",
        children=[popup_child_error],
    )
    closed_main = _FakeFrame(name="", url="https://closed.example")

    root_page = _FakePage("Root", "https://root.example", root_main, closed=False)
    popup_page = _FakePage("Popup", "https://popup.example", popup_main, closed=False)
    closed_page = _FakePage("Closed", "https://closed.example", closed_main, closed=True)

    manager = PlaywrightManager()
    manager._is_initialized = True
    cast(Any, manager)._page = root_page
    cast(Any, manager)._context = _FakeContext([root_page, popup_page, closed_page])

    snapshots = manager.collect_dom_snapshots(include_frames=True)

    assert len(snapshots) == 5

    root_docs = [s for s in snapshots if s.window_title == "Root"]
    assert len(root_docs) == 2
    assert all(s.is_popup is False for s in root_docs)
    assert any(s.frame_path == "childA" for s in root_docs)

    popup_docs = [s for s in snapshots if s.window_title == "Popup"]
    assert len(popup_docs) == 2
    assert all(s.is_popup is True for s in popup_docs)
    assert any(s.frame_path == "index=1" and s.error and s.error_type == "detached_frame" for s in popup_docs)

    assert any(s.frame_path == "main" and s.error == "page is closed" and s.error_type == "closed_page" for s in snapshots)


def test_collect_dom_snapshots_current_scope_without_frames_uses_tracked_page():
    root_main = _FakeFrame(name="", url="https://root.example", html="<html><body>root</body></html>")
    popup_main = _FakeFrame(name="", url="https://popup.example", html="<html><body>popup</body></html>")

    root_page = _FakePage("Root", "https://root.example", root_main, closed=False)
    popup_page = _FakePage("Popup", "https://popup.example", popup_main, closed=False)

    manager = PlaywrightManager()
    manager._is_initialized = True
    cast(Any, manager)._root_page = root_page
    cast(Any, manager)._page = popup_page
    cast(Any, manager)._context = _FakeContext([root_page, popup_page])

    snapshots = manager.collect_dom_snapshots(include_frames=False, scope="current")

    assert len(snapshots) == 1
    assert snapshots[0].window_title == "Popup"
    assert snapshots[0].window_url == "https://popup.example"
    assert snapshots[0].frame_path == "main"
    assert snapshots[0].is_popup is True
    assert "popup" in snapshots[0].html


def test_current_page_falls_back_to_last_open_page_when_active_page_closes():
    root_main = _FakeFrame(name="", url="https://root.example", html="<html><body>root</body></html>")
    popup_main = _FakeFrame(name="", url="https://popup.example", html="<html><body>popup</body></html>")
    extra_main = _FakeFrame(name="", url="https://extra.example", html="<html><body>extra</body></html>")

    root_page = _FakePage("Root", "https://root.example", root_main, closed=False)
    popup_page = _FakePage("Popup", "https://popup.example", popup_main, closed=False)
    extra_page = _FakePage("Extra", "https://extra.example", extra_main, closed=False)

    manager = PlaywrightManager()
    manager._is_initialized = True
    cast(Any, manager)._root_page = root_page
    cast(Any, manager)._page = popup_page
    cast(Any, manager)._context = _FakeContext([root_page, popup_page, extra_page])

    popup_page._closed = True
    manager._handle_page_closed(popup_page)

    assert manager.page is extra_page


def test_is_alive_returns_true_after_closed_page_fallback_to_open_page():
    closed_main = _FakeFrame(name="", url="https://closed.example")
    open_main = _FakeFrame(name="", url="https://open.example")
    closed_page = _FakePage("Closed", "https://closed.example", closed_main, closed=True)
    open_page = _FakePage("Open", "https://open.example", open_main, closed=False)

    manager = PlaywrightManager()
    manager._is_initialized = True
    cast(Any, manager)._page = closed_page
    cast(Any, manager)._context = _FakeContext([closed_page, open_page])

    assert manager.is_alive() is True
    assert manager.page is open_page
    assert cast(Any, manager)._current_frame is open_main
