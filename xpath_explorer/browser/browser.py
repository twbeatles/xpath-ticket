# -*- coding: utf-8 -*-
# pyright: reportAttributeAccessIssue=false, reportCallIssue=false, reportArgumentType=false, reportRedeclaration=false
"""Compatibility facade for the split Selenium browser manager."""

from xpath_explorer.browser.selenium_dom import BrowserDomMixin
from xpath_explorer.browser.selenium_driver import BrowserDriverMixin
from xpath_explorer.browser.selenium_frames import BrowserFrameMixin
from xpath_explorer.browser.selenium_picker import BrowserPickerMixin
from xpath_explorer.browser.selenium_validation import BrowserValidationMixin
from xpath_explorer.browser.selenium_windows import BrowserWindowMixin


class BrowserManager(
    BrowserDriverMixin,
    BrowserWindowMixin,
    BrowserFrameMixin,
    BrowserValidationMixin,
    BrowserPickerMixin,
    BrowserDomMixin,
):
    """Browser manager for Selenium-based exploration."""
