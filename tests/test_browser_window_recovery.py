from selenium.common.exceptions import NoSuchWindowException

from xpath_explorer.browser.browser import BrowserManager


class _FakeSwitchTo:
    def __init__(self, driver):
        self._d = driver

    def default_content(self):
        self._d._frame_stack = []

    def window(self, handle: str):
        self._d._switch_calls.append(handle)
        if handle in self._d._fail_once:
            self._d._fail_once.remove(handle)
            self._d._remove_handle(handle)
            raise NoSuchWindowException(f"closed: {handle}")
        if handle not in self._d._handles:
            raise NoSuchWindowException(f"missing: {handle}")
        self._d._current = handle


class _FakeDriver:
    def __init__(
        self,
        handles,
        current_handle: str,
        opener_handles=None,
        fail_once_handles=None,
    ):
        self._handles = list(handles)
        self._current = current_handle
        self._opener_handles = set(opener_handles or [])
        self._fail_once = set(fail_once_handles or [])
        self._frame_stack = []
        self._switch_calls = []
        self.switch_to = _FakeSwitchTo(self)

    def _remove_handle(self, handle: str):
        if handle in self._handles:
            self._handles.remove(handle)

    @property
    def current_window_handle(self):
        if self._current not in self._handles:
            raise NoSuchWindowException("current closed")
        return self._current

    @property
    def window_handles(self):
        return list(self._handles)

    @property
    def title(self):
        return f"title-{self._current}"

    @property
    def current_url(self):
        return f"https://{self._current}.example"

    def execute_script(self, script, *_args):
        if "window.opener" in script:
            return self._current in self._opener_handles
        return None


def test_recover_to_available_window_handles_disappearing_candidate():
    driver = _FakeDriver(
        handles=["main", "popup_b", "popup_a"],
        current_handle="main",
        opener_handles={"popup_a", "popup_b"},
        fail_once_handles={"popup_b"},
    )
    browser = BrowserManager()
    browser.driver = driver
    browser._root_window_handle = "main"
    browser.current_frame_path = "some/frame"

    assert browser._recover_to_available_window() is True
    assert driver.current_window_handle == "popup_a"
    assert browser.current_frame_path == ""


def test_switch_window_falls_back_when_requested_handle_missing():
    driver = _FakeDriver(
        handles=["main", "popup"],
        current_handle="main",
        opener_handles={"popup"},
    )
    browser = BrowserManager()
    browser.driver = driver
    browser._root_window_handle = "main"

    assert browser.switch_window("does-not-exist") is True
    assert driver.current_window_handle == "popup"


def test_get_windows_recovers_when_original_current_window_disappears():
    driver = _FakeDriver(
        handles=["main", "popup1", "popup2"],
        current_handle="popup1",
        opener_handles={"popup1", "popup2"},
        fail_once_handles={"popup1"},
    )
    browser = BrowserManager()
    browser.driver = driver
    browser._root_window_handle = "main"

    windows = browser.get_windows()

    handles = {window["handle"] for window in windows}
    assert handles == {"main", "popup2"}
    assert driver.current_window_handle == "popup2"
    popup2 = [w for w in windows if w["handle"] == "popup2"]
    assert popup2 and popup2[0]["is_popup"] is True
