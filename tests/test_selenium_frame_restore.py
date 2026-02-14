from dataclasses import dataclass

import pytest
from selenium.common.exceptions import NoSuchElementException, NoSuchFrameException
from selenium.webdriver.common.by import By

from xpath_browser import BrowserManager


@dataclass
class FakeFrameEl:
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
        # support id/name string, or FakeFrameEl object
        if isinstance(frame_ref, FakeFrameEl):
            frame_id = frame_ref.frame_id or frame_ref.frame_name
        else:
            frame_id = frame_ref

        # Only one iframe exists from main: "f1"
        if not self._d._frame_stack and frame_id == "f1":
            self._d._frame_stack.append("f1")
            return
        raise NoSuchFrameException(f"no such frame: {frame_id}")

    def window(self, handle: str):
        # single window only
        if handle != "w1":
            raise Exception("no such window")
        self._d._current_window = handle


class FakeElement:
    tag_name = "div"
    text = "hello world"


class FakeDriver:
    def __init__(self):
        self._frame_stack = []
        self._current_window = "w1"
        self.switch_to = _FakeSwitchTo(self)

    @property
    def current_window_handle(self):
        return self._current_window

    @property
    def window_handles(self):
        return ["w1"]

    @property
    def title(self):
        return "t"

    @property
    def current_url(self):
        return "u"

    def find_elements(self, by, value):
        if by == By.TAG_NAME and value == "iframe":
            if self._frame_stack:
                return []
            return [FakeFrameEl(frame_id="f1")]
        if by == By.XPATH:
            # count
            try:
                self.find_element(by, value)
                return [FakeElement()]
            except NoSuchElementException:
                return []
        return []

    def find_element(self, by, value):
        if by == By.XPATH:
            # element exists only in frame f1
            if self._frame_stack == ["f1"] and value == "//ok":
                return FakeElement()
            raise NoSuchElementException("not found")
        raise NoSuchElementException("unsupported")

    def execute_script(self, script, *args):
        # picker result only in frame f1
        if script.strip() == "return window.__pickerResult;":
            if self._frame_stack == ["f1"]:
                return {"xpath": "//ok", "css": "#x", "tag": "div", "text": "hi"}
            return None
        if script.strip() == "return window.__pickerActive;":
            return False
        return None


def test_validate_xpath_restores_original_frame():
    bm = BrowserManager()
    bm.driver = FakeDriver()

    # simulate that caller is currently inside frame f1
    assert bm.switch_to_frame_by_path("f1")
    assert bm.current_frame_path == "f1"
    assert bm.driver._frame_stack == ["f1"]

    res = bm.validate_xpath("//ok")
    assert res["found"] is True
    assert res["frame_path"] == "f1"

    # should be restored back to f1, not left in main
    assert bm.current_frame_path == "f1"
    assert bm.driver._frame_stack == ["f1"]


def test_get_picker_result_restores_original_frame_and_sets_frame_path():
    bm = BrowserManager()
    bm.driver = FakeDriver()

    assert bm.switch_to_frame_by_path("f1")
    assert bm.current_frame_path == "f1"

    out = bm.get_picker_result()
    assert isinstance(out, dict)
    assert out.get("frame") == "f1"

    # restored
    assert bm.current_frame_path == "f1"
    assert bm.driver._frame_stack == ["f1"]

