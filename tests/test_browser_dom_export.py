from dataclasses import dataclass

from selenium.common.exceptions import NoSuchFrameException
from selenium.webdriver.common.by import By

from xpath_explorer.browser.browser import BrowserManager


@dataclass
class _FakeFrameEl:
    frame_id: str = ""
    frame_name: str = ""

    def get_attribute(self, name: str):
        if name == "id":
            return self.frame_id
        if name == "name":
            return self.frame_name
        return None


class _FakeSwitchTo:
    def __init__(self, driver):
        self._d = driver

    def default_content(self):
        self._d._frame_stack = []

    def parent_frame(self):
        if not self._d._frame_stack:
            raise NoSuchFrameException("no parent")
        self._d._frame_stack.pop()

    def frame(self, frame_ref):
        if isinstance(frame_ref, _FakeFrameEl):
            target = frame_ref.frame_id or frame_ref.frame_name
        else:
            target = str(frame_ref)

        children = self._d._frame_tree[self._d._current_window].get(tuple(self._d._frame_stack), [])
        for child in children:
            child_id = child.frame_id or child.frame_name
            if child_id == target:
                self._d._frame_stack.append(child_id)
                return
        raise NoSuchFrameException(f"no such frame: {target}")

    def window(self, handle: str):
        if handle not in self._d._windows:
            raise Exception("no such window")
        self._d._current_window = handle
        self._d._frame_stack = []


class _FakeDriver:
    def __init__(self):
        self._windows = {
            "main": {"title": "Main Window", "url": "https://main.example", "opener": False},
            "popup": {"title": "Popup Window", "url": "https://popup.example", "opener": True},
        }
        self._current_window = "main"
        self._frame_stack = []
        self._frame_tree = {
            "main": {
                tuple(): [_FakeFrameEl(frame_id="mainf")],
                ("mainf",): [_FakeFrameEl(frame_id="nested")],
                ("mainf", "nested"): [],
            },
            "popup": {
                tuple(): [_FakeFrameEl(frame_id="popf")],
                ("popf",): [],
            },
        }
        self.switch_to = _FakeSwitchTo(self)

    @property
    def current_window_handle(self):
        return self._current_window

    @property
    def window_handles(self):
        return ["main", "popup"]

    @property
    def title(self):
        return self._windows[self._current_window]["title"]

    @property
    def current_url(self):
        return self._windows[self._current_window]["url"]

    def find_elements(self, by, value):
        if by == By.TAG_NAME and value == "iframe":
            return list(self._frame_tree[self._current_window].get(tuple(self._frame_stack), []))
        return []

    def execute_script(self, script, *args):
        if "window.opener" in script:
            return bool(self._windows[self._current_window]["opener"])
        if "document.URL" in script or "window.location.href" in script:
            path = "/".join(self._frame_stack) if self._frame_stack else "main"
            return f"{self.current_url}#{path}"
        if "document.documentElement" in script and "outerHTML" in script:
            if self._current_window == "popup" and tuple(self._frame_stack) == ("popf",):
                raise Exception("detached frame")
            path = "/".join(self._frame_stack) if self._frame_stack else "main"
            return f"<html><body>{self._current_window}:{path}</body></html>"
        return None


def test_collect_dom_snapshots_collects_popup_and_frames_and_restores_context():
    browser = BrowserManager()
    browser.driver = _FakeDriver()
    browser._root_window_handle = "main"

    browser.driver.switch_to.window("popup")
    browser.driver.switch_to.frame("popf")
    browser.current_frame_path = "popf"

    snapshots = browser.collect_dom_snapshots(include_frames=True)

    assert len(snapshots) == 5

    popup_docs = [s for s in snapshots if s.window_id == "popup"]
    assert len(popup_docs) == 2
    assert all(s.is_popup for s in popup_docs)

    main_nested = [s for s in snapshots if s.window_id == "main" and s.frame_path == "mainf/nested"]
    assert len(main_nested) == 1
    assert main_nested[0].is_popup is False
    assert "main:mainf/nested" in main_nested[0].html

    errors = [s for s in snapshots if s.error]
    assert len(errors) == 1
    assert errors[0].window_id == "popup"
    assert errors[0].frame_path == "popf"

    assert browser.driver.current_window_handle == "popup"
    assert browser.driver._frame_stack == ["popf"]
    assert browser.current_frame_path == "popf"
