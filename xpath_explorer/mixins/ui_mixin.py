# -*- coding: utf-8 -*-
# pyright: reportAttributeAccessIssue=false, reportCallIssue=false, reportArgumentType=false
"""Compatibility facade for the split UI mixins."""

from xpath_explorer.mixins.ui import (
    ExplorerUIBrowserPanelMixin,
    ExplorerUIEditorPanelMixin,
    ExplorerUIListPanelMixin,
    ExplorerUIMenuMixin,
    ExplorerUIStatusPanelMixin,
    ExplorerUIUrlPanelMixin,
    ExplorerUIWindowMixin,
)


class ExplorerUIMixin(
    ExplorerUIWindowMixin,
    ExplorerUIMenuMixin,
    ExplorerUIBrowserPanelMixin,
    ExplorerUIUrlPanelMixin,
    ExplorerUIListPanelMixin,
    ExplorerUIEditorPanelMixin,
    ExplorerUIStatusPanelMixin,
):
    """Aggregate UI mixin preserving the legacy import path."""
