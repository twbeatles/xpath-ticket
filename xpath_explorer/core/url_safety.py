# -*- coding: utf-8 -*-
"""Navigation URL normalization and scheme checks."""

from __future__ import annotations

from typing import Tuple
from urllib.parse import urlparse

_ALLOWED_SCHEMES = {"http", "https", "about", "file"}
_BLOCKED_SCHEMES = {"javascript", "data", "vbscript"}


def normalize_navigation_url(raw: str) -> Tuple[bool, str]:
    """
    Return (ok, url_or_error).

    Bare hosts become https://. about: and file: are kept. javascript:/data: are rejected.
    """
    text = (raw or "").strip()
    if not text:
        return False, "URL이 비어 있습니다."

    parsed = urlparse(text)
    scheme = (parsed.scheme or "").lower()
    if scheme in _BLOCKED_SCHEMES:
        return False, f"허용되지 않는 URL 스킴입니다: {scheme}"
    if scheme in _ALLOWED_SCHEMES:
        return True, text
    if scheme:
        return False, f"허용되지 않는 URL 스킴입니다: {scheme}"
    return True, "https://" + text
