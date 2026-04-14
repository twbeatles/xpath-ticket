# -*- coding: utf-8 -*-
# pyright: reportAttributeAccessIssue=false, reportCallIssue=false, reportArgumentType=false, reportRedeclaration=false
"""Compatibility facade for the split browser mixins."""

from xpath_explorer.mixins.browser import (
    ExplorerBrowserContextMixin,
    ExplorerBrowserExportMixin,
    ExplorerBrowserNavigationMixin,
    ExplorerBrowserPickerMixin,
    ExplorerBrowserPreviewMixin,
    ExplorerBrowserValidationMixin,
)
from xpath_explorer.mixins.browser.deps import QFileDialog, LivePreviewWorker


class ExplorerBrowserMixin(
    ExplorerBrowserContextMixin,
    ExplorerBrowserNavigationMixin,
    ExplorerBrowserValidationMixin,
    ExplorerBrowserPickerMixin,
    ExplorerBrowserPreviewMixin,
    ExplorerBrowserExportMixin,
):
    """Aggregate browser mixin preserving the legacy import path."""
