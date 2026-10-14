# -*- coding: utf-8 -*-
"""Cookie tools work on the active engine (Phase 2 parity) tests."""

import json
from types import SimpleNamespace

from PySide6.QtWidgets import QMessageBox

from xpath_explorer.mixins.data.cookies import ExplorerDataCookiesMixin


def _say_yes(monkeypatch, cookies_module):
    monkeypatch.setattr(
        cookies_module.QMessageBox, "warning",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
    )


class _DeadSelenium:
    driver = None

    def is_alive(self):
        return False


class _FakeSeleniumDriver:
    def __init__(self):
        self.saved_via = []
        self.added = []
        self.refresh_called = 0
        self.cleared = 0
        self.current_url = "https://ticket.example.com/list"

    def get_cookies(self):
        return [{"name": "sel", "value": "1", "domain": "ticket.example.com"}]

    def add_cookie(self, cookie):
        self.added.append(cookie)

    def refresh(self):
        self.refresh_called += 1

    def delete_all_cookies(self):
        self.cleared += 1


class _FakeSelenium:
    def __init__(self):
        self.driver = _FakeSeleniumDriver()

    def is_alive(self):
        return True


class _FakePlaywright:
    def __init__(self):
        self.set_calls = []
        self.cleared = 0
        self.reloaded = 0

    def is_alive(self):
        return True

    def get_cookies(self):
        return [{"name": "pw", "value": "2", "domain": "ticket.example.com"}]

    def set_cookies(self, cookies):
        self.set_calls.extend(cookies)

    def clear_cookies(self):
        self.cleared += 1

    def get_current_window_metadata(self):
        return {"handle": "p1", "title": "PW",
                "url": "https://ticket.example.com/seat", "is_popup": False}

    def reload_current_page(self):
        self.reloaded += 1
        return True


def _host(browser, pw_manager):
    toasts = []
    host = SimpleNamespace(browser=browser, pw_manager=pw_manager)
    host.toasts = toasts
    host._show_toast = lambda msg, _kind="info", *_a: toasts.append(str(msg))
    for name in ("_cookie_engine", "_report_cookie_load", "_save_cookies",
                 "_load_cookies", "_clear_cookies"):
        setattr(host, name, getattr(ExplorerDataCookiesMixin, name).__get__(host))
    return host


def test_save_cookies_uses_playwright_when_selenium_dead(tmp_path, monkeypatch):
    import xpath_explorer.mixins.data.cookies as cookies_module

    pw = _FakePlaywright()
    host = _host(_DeadSelenium(), pw)
    target = tmp_path / "cookies.json"
    _say_yes(monkeypatch, cookies_module)
    monkeypatch.setattr(
        cookies_module.QFileDialog, "getSaveFileName",
        staticmethod(lambda *a, **k: (str(target), "")),
    )

    host._save_cookies()

    saved = json.loads(target.read_text(encoding="utf-8"))
    assert saved == [{"name": "pw", "value": "2", "domain": "ticket.example.com"}]
    assert not list(tmp_path.glob("*.bak"))
    assert any("1개 저장됨" in t for t in host.toasts)


def test_save_cookies_prefers_selenium_when_both_alive(tmp_path, monkeypatch):
    import xpath_explorer.mixins.data.cookies as cookies_module

    sel = _FakeSelenium()
    pw = _FakePlaywright()
    host = _host(sel, pw)
    target = tmp_path / "cookies.json"
    _say_yes(monkeypatch, cookies_module)
    monkeypatch.setattr(
        cookies_module.QFileDialog, "getSaveFileName",
        staticmethod(lambda *a, **k: (str(target), "")),
    )

    host._save_cookies()

    saved = json.loads(target.read_text(encoding="utf-8"))
    assert saved[0]["name"] == "sel"


def test_load_cookies_into_playwright_session(tmp_path, monkeypatch):
    import xpath_explorer.mixins.data.cookies as cookies_module

    pw = _FakePlaywright()
    host = _host(_DeadSelenium(), pw)
    cookie_path = tmp_path / "cookies.json"
    cookie_path.write_text(
        json.dumps([
            {"name": "ok", "value": "1", "domain": "ticket.example.com"},
            {"name": "other", "value": "9", "domain": "unrelated.example"},
        ]),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        cookies_module.QFileDialog, "getOpenFileName",
        staticmethod(lambda *a, **k: (str(cookie_path), "")),
    )

    host._load_cookies()

    assert [c["name"] for c in pw.set_calls] == ["ok"]
    assert pw.reloaded == 1
    assert "success 1, failed 1" in host.toasts[-1]


def test_clear_cookies_on_playwright_session():
    pw = _FakePlaywright()
    host = _host(_DeadSelenium(), pw)

    host._clear_cookies()

    assert pw.cleared == 1
    assert "삭제되었습니다" in host.toasts[-1]


def test_cookie_tools_silent_when_no_engine():
    host = _host(_DeadSelenium(), None)

    host._save_cookies()
    host._load_cookies()
    host._clear_cookies()

    assert host.toasts == []
