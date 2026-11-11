# -*- coding: utf-8 -*-
"""Compatibility aggregate for split ExplorerInspectionToolsMixin."""

from xpath_explorer.mixins.tools.inspection.diagnostics import FeatureDiagnosticsMixin
from xpath_explorer.mixins.tools.inspection.diff_panel import DiffInspectionMixin
from xpath_explorer.mixins.tools.inspection.dom_diff import DomDiffInspectionMixin
from xpath_explorer.mixins.tools.inspection.network import NetworkInspectionMixin
from xpath_explorer.mixins.tools.inspection.statistics import StatisticsInspectionMixin
from xpath_explorer.mixins.tools.inspection.telemetry import TelemetryInspectionMixin


class ExplorerInspectionToolsMixin(
    FeatureDiagnosticsMixin,
    NetworkInspectionMixin,
    StatisticsInspectionMixin,
    DomDiffInspectionMixin,
    TelemetryInspectionMixin,
    DiffInspectionMixin,
):
    """Aggregate mixin preserving the legacy ExplorerInspectionToolsMixin import path."""
