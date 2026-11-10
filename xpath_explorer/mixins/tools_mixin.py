# -*- coding: utf-8 -*-
# pyright: reportAttributeAccessIssue=false, reportCallIssue=false, reportArgumentType=false
"""Compatibility facade for the split tools mixins."""

from xpath_explorer.mixins.tools import (
    ExplorerAIToolsMixin,
    ExplorerBatchToolsMixin,
    ExplorerGenerationToolsMixin,
    ExplorerHistoryToolsMixin,
    ExplorerInspectionToolsMixin,
    ExplorerLifecycleToolsMixin,
    ExplorerPlaywrightToolsMixin,
)
from xpath_explorer.mixins.tools.deps import InstallChromiumWorker, QMessageBox  # noqa: F401 -- patched via mixins.tools_mixin in toggle tests


class ExplorerToolsMixin(
    ExplorerBatchToolsMixin,
    ExplorerGenerationToolsMixin,
    ExplorerInspectionToolsMixin,
    ExplorerPlaywrightToolsMixin,
    ExplorerHistoryToolsMixin,
    ExplorerAIToolsMixin,
    ExplorerLifecycleToolsMixin,
):
    """Aggregate tools mixin preserving the legacy import path."""
