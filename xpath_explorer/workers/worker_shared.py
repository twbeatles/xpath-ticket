# -*- coding: utf-8 -*-
"""XPath Explorer worker support imports."""

import time
import logging
from typing import List, Optional, Any, Dict, cast
from threading import Event
from PyQt6.QtCore import QThread, pyqtSignal

from xpath_explorer.core.config import XPathItem
from xpath_explorer.core.constants import PICKER_POLL_INTERVAL_MS, PICKER_ACTIVE_CHECK_TICKS
from xpath_explorer.tools.ai import XPathAIAssistant
from xpath_explorer.analysis.diff import XPathDiffAnalyzer
from xpath_explorer.core.perf import perf_span

logger = logging.getLogger('XPathExplorer')

def _window_context_from_item(item: Any) -> Dict[str, str]:
    return {
        "handle": str(getattr(item, "found_window", "") or ""),
        "title": str(getattr(item, "found_window_title", "") or ""),
        "url": str(getattr(item, "found_window_url", "") or ""),
    }


def _get_browser_window_metadata(browser: Any) -> Dict[str, Any]:
    getter = getattr(browser, "get_current_window_metadata", None)
    if callable(getter):
        try:
            metadata = getter()
        except Exception:
            metadata = None
        if isinstance(metadata, dict):
            return metadata
    driver = getattr(browser, "driver", None)
    try:
        handle = str(getattr(driver, "current_window_handle", "") or "")
    except Exception:
        handle = ""
    return {
        "handle": handle,
        "title": "",
        "url": "",
        "is_popup": False,
    }


def _switch_browser_to_item_window(browser: Any, item: Any) -> tuple[bool, str]:
    context = _window_context_from_item(item)
    handle = context["handle"]
    title = context["title"]
    url = context["url"]
    if not any((handle, title, url)):
        return True, ""

    switch_context = getattr(browser, "switch_to_window_context", None)
    try:
        if callable(switch_context):
            ok = bool(switch_context(handle=handle, window_url=url, title=title))
        elif handle:
            ok = bool(browser.switch_window(handle))
        else:
            ok = True
    except Exception as e:
        return False, str(e)
    if ok:
        return True, ""
    return False, str(getattr(browser, "last_error", "") or "대상 창을 찾을 수 없습니다.")
