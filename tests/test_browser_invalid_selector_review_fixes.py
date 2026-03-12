from selenium.common.exceptions import InvalidSelectorException
from selenium.webdriver.common.by import By

from xpath_explorer.browser.browser import BrowserManager


class _SwitchTo:
    def __init__(self, driver):
        self._driver = driver

    def default_content(self):
        self._driver._frame = "main"

    def parent_frame(self):
        self._driver._frame = "main"

    def frame(self, frame_ref):
        self._driver._frame = str(frame_ref)

    def window(self, handle):
        self._driver._window = handle


class _DriverInvalidSelector:
    def __init__(self):
        self._window = "w1"
        self._frame = "main"
        self.switch_to = _SwitchTo(self)

    @property
    def current_window_handle(self):
        return self._window

    @property
    def window_handles(self):
        return [self._window]

    @property
    def title(self):
        return "t"

    @property
    def current_url(self):
        return "https://example.com"

    def find_elements(self, by, value):
        if by == By.XPATH and value == "//*[":
            raise InvalidSelectorException("bad xpath")
        if by == By.TAG_NAME and value == "iframe":
            return []
        return []


class _DriverSyntaxPass:
    def __init__(self):
        self._window = "w1"
        self._frame = "main"
        self.switch_to = _SwitchTo(self)

    @property
    def current_window_handle(self):
        return self._window

    @property
    def window_handles(self):
        return [self._window]

    @property
    def title(self):
        return "t"

    @property
    def current_url(self):
        return "https://example.com"

    def find_elements(self, by, value):
        if by == By.TAG_NAME and value == "iframe":
            return []
        if by == By.XPATH:
            return []
        return []


def test_validate_xpath_invalid_selector_returns_error_and_skips_miss_cache():
    bm = BrowserManager()
    bm.driver = _DriverInvalidSelector()
    session = bm.begin_validation_session()
    scans = {"count": 0}
    original = bm.find_element_in_all_frames

    def wrapped(xpath, max_depth=5):
        scans["count"] += 1
        return original(xpath, max_depth=max_depth)

    bm.find_element_in_all_frames = wrapped

    result = bm.validate_xpath("//*[", session=session)

    assert result["found"] is False
    assert result["error_type"] == "invalid_selector"
    assert scans["count"] == 0
    assert session.get("misses", {}) == {}


def test_validate_xpath_frame_level_invalid_selector_does_not_add_miss(monkeypatch):
    bm = BrowserManager()
    bm.driver = _DriverSyntaxPass()
    session = bm.begin_validation_session()
    miss_calls = []

    monkeypatch.setattr(bm, "_session_refresh_frame_signature", lambda _session: None)
    monkeypatch.setattr(
        bm,
        "find_element_in_all_frames",
        lambda _xpath, max_depth=5: (None, "frameA"),
    )
    monkeypatch.setattr(
        bm,
        "_try_find_in_frame",
        lambda _xpath, frame_path: {
            "found": False,
            "msg": "invalid selector",
            "error_type": "invalid_selector",
            "frame_path": frame_path,
        },
    )
    monkeypatch.setattr(bm, "_session_add_miss", lambda _session, xpath: miss_calls.append(xpath))

    result = bm.validate_xpath("//x", session=session)

    assert result["found"] is False
    assert result["error_type"] == "invalid_selector"
    assert miss_calls == []
