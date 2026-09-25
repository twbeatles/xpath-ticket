# -*- coding: utf-8 -*-
"""Click actions (Selenium/Playwright) + DOM analysis bundle tests."""

import json
import zipfile

from selenium.common.exceptions import NoSuchElementException, NoSuchFrameException
from selenium.webdriver.common.by import By

from xpath_explorer.browser.browser import BrowserManager
from xpath_explorer.browser.dom_export import DomSnapshot, save_dom_bundle
from xpath_explorer.browser.playwright_parts.dom.actions import (
    PlaywrightDomActionsMixin,
)


class _FakeFrameEl:
    def __init__(self, frame_id=""):
        self.frame_id = frame_id

    def get_attribute(self, name):
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

    def window(self, handle):
        if handle != "w1":
            raise Exception("no such window")
        self._driver._current_window = handle


class _ClickableElement:
    tag_name = "button"
    text = "예매"
    clicked = False

    def click(self):
        type(self).clicked = True


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
                return [_ClickableElement()]
            except NoSuchElementException:
                return []
        return []

    def find_element(self, by, value):
        if by == By.XPATH and self._frame_stack == ["f1"] and value == "//ok":
            return _ClickableElement()
        raise NoSuchElementException("not found")

    def execute_script(self, *_args):
        return None


def _selenium_manager():
    manager = BrowserManager()
    manager.driver = _FakeDriver()
    return manager


def test_selenium_click_element_success_clears_error():
    _ClickableElement.clicked = False
    manager = _selenium_manager()

    assert manager.click_element("//ok") is True
    assert _ClickableElement.clicked is True
    assert manager.last_error == ""


def test_selenium_click_element_missing_sets_last_error():
    manager = _selenium_manager()

    assert manager.click_element("//missing") is False
    assert "요소를 찾을 수 없습니다" in manager.last_error


class _FlakyDriver(_FakeDriver):
    """First two finds miss (frame reload race), then the element appears."""

    def __init__(self):
        super().__init__()
        self.find_calls = 0

    def find_element(self, by, value):
        self.find_calls += 1
        if self.find_calls <= 2:
            raise NoSuchElementException("transient miss")
        return super().find_element(by, value)


def test_selenium_click_element_retries_transient_miss():
    _ClickableElement.clicked = False
    manager = BrowserManager()
    manager.driver = _FlakyDriver()

    # frame_path를 주면 탐색을 건너뛰어 클릭 단계의 재시도 루프를 직접 탄다.
    assert manager.click_element("//ok", frame_path="f1") is True
    assert _ClickableElement.clicked is True
    assert manager.driver.find_calls == 3
    assert manager.last_error == ""


def test_selenium_click_element_bad_frame_sets_last_error():
    manager = _selenium_manager()

    assert manager.click_element("//ok", frame_path="no-such-frame") is False
    assert "프레임 전환 실패" in manager.last_error


class _FakeLocator:
    def __init__(self, frame, fail=False):
        self._frame = frame
        self._fail = fail

    def scroll_into_view_if_needed(self, timeout=None):
        self._frame.scroll_calls.append(timeout)

    def click(self, timeout=None):
        self._frame.click_calls.append(timeout)
        if self._fail:
            raise RuntimeError("no matching node")


class _FakePwFrame:
    def __init__(self, fail=False):
        self._fail = fail
        self.seen_selectors = []
        self.scroll_calls = []
        self.click_calls = []

    def locator(self, selector):
        self.seen_selectors.append(selector)
        return _FakeLocator(self, fail=self._fail)


class _PwClickStub(PlaywrightDomActionsMixin):
    def __init__(self, main_fail=True, sub_fail=False):
        self.last_error = ""
        self._main = _FakePwFrame(fail=main_fail)
        self._sub = _FakePwFrame(fail=sub_fail)
        self._page = object()

    def is_alive(self):
        return True

    def _get_current_page(self):
        return self._page

    def _get_frame(self):
        return self._main

    def _walk_frame_paths(self, page):
        assert page is self._page
        return [(self._main, "main"), (self._sub, "sub")]


def test_playwright_click_prefers_explicit_frame():
    stub = _PwClickStub(main_fail=True, sub_fail=False)

    assert stub.click_element("//ok", frame_path="sub") is True
    assert stub._sub.seen_selectors == ["xpath=//ok"]
    assert stub.last_error == ""


def test_playwright_click_falls_back_across_frames():
    stub = _PwClickStub(main_fail=True, sub_fail=False)

    assert stub.click_element("//ok") is True
    assert stub._main.seen_selectors == ["xpath=//ok"]
    assert stub._sub.seen_selectors == ["xpath=//ok"]


def test_playwright_click_all_miss_sets_last_error():
    stub = _PwClickStub(main_fail=True, sub_fail=True)

    assert stub.click_element("//missing") is False
    assert stub.last_error != ""


def test_save_dom_bundle_roundtrip(tmp_path):
    snapshots = [
        DomSnapshot(
            engine="selenium",
            window_id="w1",
            window_title="메인",
            window_url="https://example.com",
            is_popup=False,
            frame_path="main",
            frame_label="main",
            document_url="https://example.com/list",
            html="<html><body>목록</body></html>",
        ),
        DomSnapshot(
            engine="selenium",
            window_id="w1",
            window_title="메인",
            window_url="https://example.com",
            is_popup=False,
            frame_path="f1",
            frame_label="f1",
            document_url="",
            html="",
            error="frame switch failed: f1",
            error_type="frames_scan_failed",
        ),
    ]
    out = tmp_path / "dom_bundle.zip"

    summary = save_dom_bundle(
        snapshots,
        str(out),
        source_label="Selenium",
        scope="all",
        selected_window_title="메인",
        selected_window_url="https://example.com",
    )

    assert summary["documents"] == 2
    assert summary["failed"] == 1
    with zipfile.ZipFile(out) as bundle:
        names = set(bundle.namelist())
        assert {"report.htm", "manifest.json"} <= names
        manifest = json.loads(bundle.read("manifest.json").decode("utf-8"))
        assert manifest["total_documents"] == 2
        assert manifest["failed_documents"] == 1
        assert manifest["selected_window_title"] == "메인"
        first, second = manifest["documents"]
        assert first["frame_path"] == "main"
        assert first["html_size"] == len("<html><body>목록</body></html>")
        assert second["error_type"] == "frames_scan_failed"
        assert first["file"] in names and second["file"] in names
        assert "목록" in bundle.read(first["file"]).decode("utf-8")
