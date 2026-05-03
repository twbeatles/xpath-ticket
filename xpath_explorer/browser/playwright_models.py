# -*- coding: utf-8 -*-
"""Shared Playwright data models and type aliases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypeAlias

PlaywrightBrowserType: TypeAlias = Any
PlaywrightBrowserContextType: TypeAlias = Any
PlaywrightPageType: TypeAlias = Any

@dataclass
class ScannedElement:
    """Scanned element data."""
    xpath: str
    css_selector: str
    tag: str
    text: str
    element_id: str
    element_name: str
    element_class: str
    is_visible: bool
    is_enabled: bool
    frame_path: str = ""
    window_handle: str = ""
    window_title: str = ""
    window_url: str = ""
    source_engine: str = "playwright"

@dataclass
class NetworkRequest:
    """Captured network request data."""
    url: str
    method: str
    resource_type: str
    status: int = 0
    response_size: int = 0
    response_body: str = ""
