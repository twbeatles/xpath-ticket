import xpath_explorer.browser.playwright as xp


class _FakeBrowser:
    def __init__(self):
        self.closed = False

    def new_context(self, **_kwargs):
        raise RuntimeError("context create failed")

    def close(self):
        self.closed = True


class _FakeChromium:
    def __init__(self, browser):
        self._browser = browser

    def launch(self, **_kwargs):
        return self._browser


class _FakePlaywright:
    def __init__(self, browser):
        self.chromium = _FakeChromium(browser)
        self.stopped = False

    def stop(self):
        self.stopped = True


class _FakeSyncPlaywright:
    def __init__(self, playwright):
        self._playwright = playwright

    def start(self):
        return self._playwright


def test_launch_cleans_up_partial_resources_on_context_failure(monkeypatch):
    fake_browser = _FakeBrowser()
    fake_playwright = _FakePlaywright(fake_browser)

    monkeypatch.setattr(xp, "PLAYWRIGHT_AVAILABLE", True)
    monkeypatch.setattr(xp, "sync_playwright", lambda: _FakeSyncPlaywright(fake_playwright))

    manager = xp.PlaywrightManager()
    ok = manager.launch(headless=True, stealth=False)

    assert ok is False
    assert "context create failed" in manager.last_error
    assert fake_browser.closed is True
    assert fake_playwright.stopped is True
    assert manager._playwright is None
    assert manager._browser is None
    assert manager._context is None
    assert manager._page is None
    assert manager._is_initialized is False
