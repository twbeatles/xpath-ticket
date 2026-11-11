# -*- coding: utf-8 -*-
"""Compatibility aggregate for split BrowserValidationMixin."""

from xpath_explorer.browser.selenium_validation_parts.element_info import (
    SeleniumElementInfoMixin,
)
from xpath_explorer.browser.selenium_validation_parts.lookup import (
    SeleniumValidationLookupMixin,
)
from xpath_explorer.browser.selenium_validation_parts.session import (
    SeleniumValidationSessionMixin,
)
from xpath_explorer.browser.selenium_validation_parts.visual import (
    SeleniumValidationVisualMixin,
)


class BrowserValidationMixin(
    SeleniumValidationSessionMixin,
    SeleniumValidationLookupMixin,
    SeleniumElementInfoMixin,
    SeleniumValidationVisualMixin,
):
    """Aggregate mixin preserving the legacy BrowserValidationMixin import path."""
