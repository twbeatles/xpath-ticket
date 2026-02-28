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

    def title(self):
        return self._title

    def is_closed(self):
        return self._closed

    def evaluate(self, _script):
        if self._closed:
            raise Exception("page closed")
        return True


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
    manager._page = root_page
    manager._context = _FakeContext([root_page, popup_page, closed_page])

    snapshots = manager.collect_dom_snapshots(include_frames=True)

    assert len(snapshots) == 5

    root_docs = [s for s in snapshots if s.window_title == "Root"]
    assert len(root_docs) == 2
    assert all(s.is_popup is False for s in root_docs)
    assert any(s.frame_path == "childA" for s in root_docs)

    popup_docs = [s for s in snapshots if s.window_title == "Popup"]
    assert len(popup_docs) == 2
    assert all(s.is_popup is True for s in popup_docs)
    assert any(s.frame_path == "index=1" and s.error for s in popup_docs)

    assert any(s.frame_path == "main" and s.error == "page is closed" for s in snapshots)
