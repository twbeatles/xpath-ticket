# -*- coding: utf-8 -*-
"""Split internals for PlaywrightDomMixin."""

from xpath_explorer.browser.playwright_parts.dom.actions import PlaywrightDomActionsMixin
from xpath_explorer.browser.playwright_parts.dom.snapshots import PlaywrightDomSnapshotMixin
from xpath_explorer.browser.playwright_parts.dom.frames import PlaywrightDomFrameMixin

__all__ = [
    "PlaywrightDomActionsMixin",
    "PlaywrightDomSnapshotMixin",
    "PlaywrightDomFrameMixin",
]
