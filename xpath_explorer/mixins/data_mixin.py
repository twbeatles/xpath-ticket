# -*- coding: utf-8 -*-
# pyright: reportAttributeAccessIssue=false, reportCallIssue=false, reportArgumentType=false
"""Compatibility facade for the split data mixins."""

from xpath_explorer.mixins.data import (
    ExplorerDataCookiesMixin,
    ExplorerDataEditorMixin,
    ExplorerDataFilesMixin,
    ExplorerDataFiltersMixin,
    ExplorerDataHistoryMixin,
    ExplorerDataSettingsMixin,
)
from xpath_explorer.mixins.data.deps import QFileDialog


class ExplorerDataMixin(
    ExplorerDataSettingsMixin,
    ExplorerDataFiltersMixin,
    ExplorerDataEditorMixin,
    ExplorerDataFilesMixin,
    ExplorerDataHistoryMixin,
    ExplorerDataCookiesMixin,
):
    """Aggregate data mixin preserving the legacy import path."""
