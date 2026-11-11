# -*- coding: utf-8 -*-
"""Split internals for PlaywrightLifecycleMixin."""

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

__all__ = [
    "PlaywrightLifecycleStateMixin",
    "PlaywrightInstallMixin",
    "PlaywrightLaunchMixin",
    "PlaywrightNavigationMixin",
]
