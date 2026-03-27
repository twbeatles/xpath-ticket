from dataclasses import dataclass

from selenium.common.exceptions import NoSuchElementException, NoSuchFrameException
from selenium.webdriver.common.by import By

from xpath_explorer.browser.browser import BrowserManager


@dataclass
class _FakeFrameEl:
    frame_id: str = ""

    def get_attribute(self, name: str):
        if name == "id":
            return self.frame_id
        return None


class _FakeSwitchTo:
    def __init__(self, driver):
        self._driver = driver

    def default_content(self):
        self._driver._frame_stack = []

    def parent_frame(self):
        if not self._driver._frame_stack:
            raise NoSuchFrameException("no parent")
        self._driver._frame_stack.pop()

    def frame(self, frame_ref):
        frame_id = frame_ref.frame_id if isinstance(frame_ref, _FakeFrameEl) else frame_ref
        if not self._driver._frame_stack and frame_id == "f1":
            self._driver._frame_stack.append("f1")
            return
        raise NoSuchFrameException(f"no such frame: {frame_id}")

    def window(self, handle: str):
        if handle != "w1":
            raise Exception("no such window")
        self._driver._current_window = handle


class _FakeElement:
    tag_name = "button"
    text = "예매"

    def screenshot(self, _save_path):
        return True


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
        return "window"

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
        if by == By.XPATH and self._frame_stack == ["f1"] and value == "//ok":
            return _FakeElement()
        raise NoSuchElementException("not found")

    def execute_script(self, *_args):
        return None


def test_highlight_sets_last_error_when_element_missing():
    manager = BrowserManager()
    manager.driver = _FakeDriver()

    ok = manager.highlight("//missing", frame_path="f1")

    assert ok is False
    assert "요소를 찾을 수 없습니다" in manager.last_error


def test_count_elements_sets_last_error_when_frame_switch_fails():
    manager = BrowserManager()
    manager.driver = _FakeDriver()

    count = manager.count_elements("//ok", frame_path="missing")

    assert count == -1
    assert "프레임 전환 실패" in manager.last_error


def test_screenshot_sets_last_error_when_element_missing():
    manager = BrowserManager()
    manager.driver = _FakeDriver()

    ok = manager.screenshot_element("//missing", "capture.png", frame_path="f1")

    assert ok is False
    assert "스크린샷 대상 요소 없음" in manager.last_error
