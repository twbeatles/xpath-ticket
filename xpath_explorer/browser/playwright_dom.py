# -*- coding: utf-8 -*-
"""Compatibility aggregate for split PlaywrightDomMixin."""

from xpath_explorer.browser.playwright_parts.dom.actions import (
    PlaywrightDomActionsMixin,
)
from xpath_explorer.browser.playwright_parts.dom.frames import PlaywrightDomFrameMixin
from xpath_explorer.browser.playwright_parts.dom.snapshots import (
    PlaywrightDomSnapshotMixin,
)


class PlaywrightDomMixin(
    PlaywrightDomActionsMixin,
    PlaywrightDomSnapshotMixin,
    PlaywrightDomFrameMixin,
):
    """Aggregate mixin preserving the legacy PlaywrightDomMixin import path."""
