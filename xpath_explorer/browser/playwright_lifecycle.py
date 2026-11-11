# -*- coding: utf-8 -*-
"""Compatibility aggregate for split PlaywrightLifecycleMixin."""

from xpath_explorer.browser.playwright_parts.lifecycle.install import (
    PlaywrightInstallMixin,
)
from xpath_explorer.browser.playwright_parts.lifecycle.launch import (
    PlaywrightLaunchMixin,
)
from xpath_explorer.browser.playwright_parts.lifecycle.navigation import (
    PlaywrightNavigationMixin,
)
from xpath_explorer.browser.playwright_parts.lifecycle.state import (
    PlaywrightLifecycleStateMixin,
)


class PlaywrightLifecycleMixin(
    PlaywrightLifecycleStateMixin,
    PlaywrightInstallMixin,
    PlaywrightLaunchMixin,
    PlaywrightNavigationMixin,
):
    """Aggregate mixin preserving the legacy PlaywrightLifecycleMixin import path."""
