from xpath_explorer.core.cookie_safety import (
    cookie_matches_url,
    partition_cookies_for_url,
    sanitize_cookie_for_selenium,
)


def test_cookie_matches_url_allows_suffix_and_exact_host():
    assert cookie_matches_url(".example.com", "https://www.example.com/login") is True
    assert cookie_matches_url("example.com", "https://example.com/") is True
    assert cookie_matches_url("other.com", "https://example.com/") is False
    assert cookie_matches_url("example.com", "") is True


def test_sanitize_cookie_for_selenium_strips_incompatible_fields():
    cleaned = sanitize_cookie_for_selenium(
        {
            "name": "sid",
            "value": "abc",
            "domain": ".example.com",
            "sameSite": "None",
            "storeId": "0",
            "id": 1,
        }
    )
    assert cleaned["name"] == "sid"
    assert "sameSite" not in cleaned
    assert "storeId" not in cleaned
    assert "id" not in cleaned


def test_partition_cookies_for_url_separates_domain_mismatches():
    cookies = [
        {"name": "ok", "domain": "example.com"},
        {"name": "skip", "domain": "evil.test"},
        "not-a-dict",
    ]
    accepted, rejected = partition_cookies_for_url(cookies, "https://www.example.com/")
    assert [c["name"] for c in accepted] == ["ok"]
    assert len(rejected) == 2
