import xpath_playwright as xp


def test_network_analyzer_importable():
    from xpath_playwright import NetworkAnalyzer  # noqa: F401


def test_network_analyzer_flow(monkeypatch):
    calls = {}

    class FakeManager:
        def __init__(self):
            self._browser = object()

        def launch(self, headless=False, stealth=True):
            calls["launch"] = (headless, stealth)
            return True

        def navigate(self, url):
            calls["url"] = url
            return True

        def start_network_monitoring(self, filter_types=None):
            calls["capture_started"] = True

        def stop_network_monitoring(self):
            calls["capture_stopped"] = True
            return [
                xp.NetworkRequest(
                    url="https://example.com/api",
                    method="GET",
                    resource_type="xhr",
                    status=200,
                    response_size=123,
                )
            ]

        def close(self):
            calls["closed"] = True

    monkeypatch.setattr(xp, "PlaywrightManager", FakeManager)
    monkeypatch.setattr(xp, "PLAYWRIGHT_AVAILABLE", True)

    analyzer = xp.NetworkAnalyzer()
    assert analyzer.is_playwright_available()
    assert analyzer.start_browser("https://example.com", headless=True)

    analyzer.start_capture()
    rows = analyzer.stop_capture()
    analyzer.close()

    assert rows
    assert rows[0].response_size == 123
    assert calls["launch"] == (True, True)
    assert calls["url"] == "https://example.com"
    assert calls["capture_started"] is True
    assert calls["capture_stopped"] is True
    assert calls["closed"] is True
