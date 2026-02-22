from dataclasses import dataclass

from selenium.common.exceptions import NoSuchElementException, NoSuchFrameException
from selenium.webdriver.common.by import By

from xpath_browser import BrowserManager


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
            frame_id = frame_ref.frame_id or frame_ref.frame_name
        else:
            frame_id = frame_ref
        if not self._d._frame_stack and frame_id == "f1":
            self._d._frame_stack.append("f1")
            return
        raise NoSuchFrameException(f"no such frame: {frame_id}")

    def window(self, handle: str):
        if handle != "w1":
            raise Exception("no such window")
        self._d._current_window = handle


class _FakeElement:
    tag_name = "div"
    text = "ok"


class _FakeDriver:
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
        return "https://example.com"

    def find_elements(self, by, value):
        if by == By.TAG_NAME and value == "iframe":
            if self._frame_stack:
                return []
            return [_FakeFrameEl(frame_id="f1")]
        if by == By.XPATH:
            try:
                self.find_element(by, value)
                return [_FakeElement()]
            except NoSuchElementException:
                return []
        return []

    def find_element(self, by, value):
        if by == By.XPATH:
            if self._frame_stack == ["f1"] and value == "//ok":
                return _FakeElement()
            raise NoSuchElementException("not found")
        raise NoSuchElementException("unsupported")

    def execute_script(self, script, *args):
        return None


def test_validation_session_reuses_frame_hint():
    bm = BrowserManager()
    bm.driver = _FakeDriver()

    call_count = {"n": 0}
    orig = bm.find_element_in_all_frames

    def wrapped(xpath, max_depth=5):
        call_count["n"] += 1
        return orig(xpath, max_depth=max_depth)

    bm.find_element_in_all_frames = wrapped

    session = {"frames": ["main"], "hints": {}, "misses": set()}

    first = bm.validate_xpath("//ok", session=session)
    second = bm.validate_xpath("//ok", session=session)

    assert first["found"] is True
    assert second["found"] is True
    assert call_count["n"] == 1
    assert session["hints"]["//ok"] == "f1"

