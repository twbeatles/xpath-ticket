# -*- coding: utf-8 -*-
# pyright: reportArgumentType=false
"""Click-test confirmation gate (ISSUE-002) regression tests."""

from types import SimpleNamespace

from PySide6.QtWidgets import QMessageBox

from xpath_explorer.mixins.browser import validation as validation_module
from xpath_explorer.mixins.browser.context import ExplorerBrowserContextMixin
from xpath_explorer.mixins.browser.validation import ExplorerBrowserValidationMixin


class _FakeBrowser:
    def __init__(self):
        self.click_calls = []
        self.last_error = ""

    def is_alive(self):
        return True

    def click_element(self, xpath, frame_path=None):
        self.click_calls.append((xpath, frame_path))
        return True


class _FakeText:
    def __init__(self, value=""):
        self._value = value
        self.written = []

    def toPlainText(self):
        return self._value

    def setPlainText(self, text):
        self.written.append(text)


def _host(browser):
    toasts = []
    host = SimpleNamespace(
        input_xpath=_FakeText("//ok"),
        txt_result=_FakeText(),
        browser=browser,
        pw_manager=None,
        _editing_source_engine="",
        refreshed=[],
        _show_toast=lambda msg, _kind="info", *_a: toasts.append(msg),
        _ensure_window_context_for_action=lambda: True,
        _resolve_active_frame_path=lambda: None,
        _refresh_windows=lambda: host.refreshed.append(True),
    )
    host.toasts = toasts
    host._active_validation_browser = (
        ExplorerBrowserContextMixin._active_validation_browser.__get__(host)
    )
    host._active_source_engine = (
        ExplorerBrowserContextMixin._active_source_engine.__get__(host)
    )
    host._confirm_click_test = (
        ExplorerBrowserValidationMixin._confirm_click_test.__get__(host)
    )
    return host


def test_click_test_cancelled_when_confirm_declined():
    browser = _FakeBrowser()
    host = _host(browser)
    host._confirm_click_test = lambda: False

    ExplorerBrowserValidationMixin._click_test_xpath(host)

    assert browser.click_calls == []
    assert host.txt_result.written == []


def test_click_test_runs_and_refreshes_when_confirmed():
    browser = _FakeBrowser()
    host = _host(browser)
    host._confirm_click_test = lambda: True

    ExplorerBrowserValidationMixin._click_test_xpath(host)

    assert browser.click_calls == [("//ok", None)]
    assert any("클릭 성공" in text for text in host.txt_result.written)
    assert host.refreshed == [True]


def test_confirm_click_test_maps_dialog_result(monkeypatch):
    host = SimpleNamespace()

    monkeypatch.setattr(
        validation_module.QMessageBox, "question",
        staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.Yes),
    )
    assert ExplorerBrowserValidationMixin._confirm_click_test(host) is True

    monkeypatch.setattr(
        validation_module.QMessageBox, "question",
        staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.No),
    )
    assert ExplorerBrowserValidationMixin._confirm_click_test(host) is False
