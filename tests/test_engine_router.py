from types import SimpleNamespace

from xpath_explorer.browser.engine_router import resolve_browser_for_item
from xpath_explorer.core.config import XPathItem


class _Alive:
    def is_alive(self):
        return True


class _Dead:
    def is_alive(self):
        return False


def test_resolve_browser_for_item_uses_playwright_when_alive():
    selenium = _Alive()
    playwright = _Alive()
    item = XPathItem(name="btn", xpath="//button", category="common", source_engine="playwright")

    browser, engine = resolve_browser_for_item(selenium, playwright, item)

    assert browser is playwright
    assert engine == "playwright"


def test_resolve_browser_for_item_returns_none_when_playwright_disconnected():
    selenium = _Alive()
    item = SimpleNamespace(source_engine="playwright")

    browser, engine = resolve_browser_for_item(
        selenium, _Dead(), item, fallback_selenium=False
    )

    assert browser is None
    assert engine == "playwright"


def test_resolve_browser_for_item_falls_back_to_selenium_when_playwright_down():
    selenium = _Alive()
    item = SimpleNamespace(source_engine="playwright")

    browser, engine = resolve_browser_for_item(selenium, _Dead(), item)

    assert browser is selenium
    assert engine == "selenium"


def test_resolve_browser_for_item_defaults_to_selenium():
    selenium = _Alive()
    item = XPathItem(name="btn", xpath="//button", category="common")

    browser, engine = resolve_browser_for_item(selenium, _Alive(), item)

    assert browser is selenium
    assert engine == "selenium"
