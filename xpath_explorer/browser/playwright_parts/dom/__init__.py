# -*- coding: utf-8 -*-
"""Split internals for PlaywrightDomMixin."""

from xpath_explorer.browser.playwright_parts.dom.actions import (
    PlaywrightDomActionsMixin,
)
from xpath_explorer.browser.playwright_parts.dom.frames import PlaywrightDomFrameMixin
from xpath_explorer.browser.playwright_parts.dom.snapshots import (
    PlaywrightDomSnapshotMixin,
)

__all__ = [
    "PlaywrightDomActionsMixin",
    "PlaywrightDomSnapshotMixin",
    "PlaywrightDomFrameMixin",
]
