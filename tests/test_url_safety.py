from xpath_explorer.core.url_safety import normalize_navigation_url


def test_normalize_navigation_url_adds_https_for_bare_hosts():
    assert normalize_navigation_url("example.com") == (True, "https://example.com")
    assert normalize_navigation_url("  example.com/path ") == (True, "https://example.com/path")


def test_normalize_navigation_url_keeps_allowed_schemes():
    assert normalize_navigation_url("https://example.com") == (True, "https://example.com")
    assert normalize_navigation_url("http://example.com") == (True, "http://example.com")
    assert normalize_navigation_url("about:blank") == (True, "about:blank")
    assert normalize_navigation_url("file:///C:/tmp/page.html") == (True, "file:///C:/tmp/page.html")


def test_normalize_navigation_url_rejects_dangerous_schemes():
    ok, value = normalize_navigation_url("javascript:alert(1)")
    assert ok is False
    assert "javascript" in value.lower()

    ok, value = normalize_navigation_url("data:text/html,hi")
    assert ok is False
    assert "data" in value.lower()


def test_normalize_navigation_url_rejects_empty():
    ok, value = normalize_navigation_url("   ")
    assert ok is False
    assert value
