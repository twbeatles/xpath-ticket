# -*- coding: utf-8 -*-
"""Compatibility aggregate for split ExplorerBatchToolsMixin."""

from xpath_explorer.mixins.tools.batch.runner import BatchRunnerMixin
from xpath_explorer.mixins.tools.batch.scenario import BatchScenarioMixin
from xpath_explorer.mixins.tools.batch.reports import BatchReportMixin


class ExplorerBatchToolsMixin(
    BatchRunnerMixin,
    BatchScenarioMixin,
    BatchReportMixin,
):
    """Aggregate mixin preserving the legacy ExplorerBatchToolsMixin import path."""
