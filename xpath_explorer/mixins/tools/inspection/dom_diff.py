# -*- coding: utf-8 -*-
# pyright: reportAttributeAccessIssue=false, reportCallIssue=false, reportArgumentType=false
"""XPath Explorer mixin module (auto-split from legacy main file)."""

import csv
import json
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from xpath_explorer.qt_compat import (
    QAction,
    QApplication,
    QAbstractItemView,
    QColor,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    Qt,
    QTimer,
    QVBoxLayout,
    QWidget,
)

from xpath_explorer.core.constants import (
    WORKER_WAIT_TIMEOUT,
    category_to_label,
)
from xpath_explorer.core.config import XPathItem
from xpath_explorer.workers.background import (
    PickerWatcher,
    ValidateWorker,
    LivePreviewWorker,
    AIGenerateWorker,
    DiffAnalyzeWorker,
    BatchTestWorker,
    BatchScenarioWorker,
    InstallChromiumWorker,
)
from xpath_explorer.core.perf import perf_span, log_perf_summary
from xpath_explorer.tools.codegen import CodeTemplate, XPathTemplate
from xpath_explorer.browser.dom_export import (
    render_dom_report_htm,
    render_dom_diff_report_htm,
    diff_dom_snapshots,
)

from xpath_explorer.runtime import logger, error_telemetry


class DomDiffInspectionMixin:
    def _collect_active_dom_snapshots(
        self,
        *,
        include_frames: bool = True,
        scope: str = "all",
    ) -> Tuple[List[Any], str]:
        """현재 활성 브라우저(Selenium/Playwright)의 DOM 스냅샷 수집."""
        if self.browser.is_alive():
            return self.browser.collect_dom_snapshots(include_frames=include_frames, scope=scope), "Selenium"
        if self.pw_manager and self.pw_manager.is_alive():
            return self.pw_manager.collect_dom_snapshots(include_frames=include_frames, scope=scope), "Playwright"
        return [], ""

    def _export_dom_diff_report(self):
        """기준선 대비 현재 DOM 비교 리포트 생성/저장."""
        snapshots, source = self._collect_active_dom_snapshots()
        if not snapshots:
            self._show_toast("활성 브라우저가 없습니다. Selenium 또는 Playwright를 먼저 연결하세요.", "warning")
            return

        baseline = list(getattr(self, "_dom_diff_baseline", []) or [])
        if not baseline:
            self._dom_diff_baseline = list(snapshots)
            self._dom_diff_source = source
            self._show_toast("DOM 기준선을 저장했습니다. 변경 후 다시 실행하면 diff 리포트를 생성합니다.", "success", 3500)
            return

        baseline_source = str(getattr(self, "_dom_diff_source", "") or "")
        if baseline_source and baseline_source != source:
            self._dom_diff_baseline = list(snapshots)
            self._dom_diff_source = source
            self._show_toast(
                f"DOM 기준선 소스가 변경되었습니다 ({baseline_source} -> {source}). 기준선을 재설정했습니다.",
                "warning",
                4500,
            )
            return

        default_name = f"dom_diff_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.htm"
        fname, _ = QFileDialog.getSaveFileName(
            self,
            "DOM 비교 리포트 저장",
            default_name,
            "HTM 파일 (*.htm *.html)",
        )
        if not fname:
            return
        if not fname.lower().endswith((".htm", ".html")):
            fname += ".htm"

        try:
            report = render_dom_diff_report_htm(
                baseline,
                snapshots,
                source_label=f"{source} DOM",
            )
            with open(fname, "w", encoding="utf-8") as f:
                f.write(report)

            changes = diff_dom_snapshots(baseline, snapshots)
            changed_count = len(changes)
            self._dom_diff_baseline = list(snapshots)
            self._dom_diff_source = source
            self._show_toast(
                f"DOM 비교 리포트 저장 완료: {fname} (변경 {changed_count}건)",
                "success",
                5000,
            )
        except Exception as e:
            logger.error(f"DOM 비교 리포트 저장 실패: {e}")
            self._show_toast(f"DOM 비교 리포트 저장 실패: {e}", "error")
