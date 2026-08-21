# -*- coding: utf-8 -*-
"""Cookie load/save helpers."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse

_STRIP_KEYS = ("sameSite", "storeId", "id")


def cookie_matches_url(cookie_domain: str, page_url: str) -> bool:
    host = (urlparse(page_url).hostname or "").lower()
    domain = (cookie_domain or "").lstrip(".").lower()
    if not domain or not host:
        return True
    return host == domain or host.endswith("." + domain)


def sanitize_cookie_for_selenium(cookie: Dict[str, Any]) -> Dict[str, Any]:
    cleaned = dict(cookie)
    for key in _STRIP_KEYS:
        cleaned.pop(key, None)
    return cleaned


def partition_cookies_for_url(
    cookies: List[Any],
    page_url: str,
) -> Tuple[List[Dict[str, Any]], List[Any]]:
    accepted: List[Dict[str, Any]] = []
    rejected: List[Any] = []
    for cookie in cookies:
        if not isinstance(cookie, dict):
            rejected.append(cookie)
            continue
        domain = str(cookie.get("domain", "") or "")
        if cookie_matches_url(domain, page_url):
            accepted.append(sanitize_cookie_for_selenium(cookie))
        else:
            rejected.append(cookie)
    return accepted, rejected
