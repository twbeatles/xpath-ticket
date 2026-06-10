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


class DiffInspectionMixin:
    def _show_diff_analyzer(self):
        """Diff 분석 다이얼로그"""
        if not self.browser.is_alive():
            self._show_toast("브라우저를 먼저 연결하세요.", "warning")
            return

        if not self.config.items:
            self._show_toast("분석할 항목이 없습니다.", "warning")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("🔍 XPath 변경 감지 (Diff 분석)")
        dialog.resize(800, 550)

        layout = QVBoxLayout(dialog)

        # 분석 버튼
        btn_analyze = QPushButton("🔍 전체 분석 실행")
        btn_analyze.setObjectName("warning")
        btn_analyze.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(btn_analyze)

        # 요약 라벨
        lbl_summary = QLabel("분석 버튼을 클릭하여 시작하세요.")
        lbl_summary.setStyleSheet("font-size: 14px; padding: 10px;")
        layout.addWidget(lbl_summary)

        # 결과 테이블
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["상태", "항목", "변경 사항", "XPath"])
        diff_hh = table.horizontalHeader()
        if diff_hh is not None:
            diff_hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        table.setColumnWidth(0, 50)
        table.setColumnWidth(1, 120)
        table.setColumnWidth(3, 200)
        diff_vh = table.verticalHeader()
        if diff_vh is not None:
            diff_vh.setVisible(False)
        layout.addWidget(table)

        def _render_diff_results(results):
            table.setUpdatesEnabled(False)
            try:
                table.setRowCount(len(results))
                unchanged = modified = missing = 0
                for row, result in enumerate(results):
                    status_item = QTableWidgetItem(result.status_icon)
                    status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    table.setItem(row, 0, status_item)

                    table.setItem(row, 1, QTableWidgetItem(result.item_name))

                    changes_text = ", ".join(result.changes) if result.changes else "-"
                    table.setItem(row, 2, QTableWidgetItem(changes_text))

                    xpath_short = result.xpath[:40] + "..." if len(result.xpath) > 40 else result.xpath
                    xpath_item = QTableWidgetItem(xpath_short)
                    xpath_item.setToolTip(result.xpath)
                    table.setItem(row, 3, xpath_item)

                    if result.status == "unchanged":
                        unchanged += 1
                    elif result.status == "modified":
                        modified += 1
                    elif result.status == "missing":
                        missing += 1
                lbl_summary.setText(f"분석 완료: ✅ 변경없음 {unchanged}개 | ⚠️ 수정됨 {modified}개 | ❌ 찾지못함 {missing}개")
            finally:
                table.setUpdatesEnabled(True)

        def _on_diff_progress(_value, message):
            lbl_summary.setText(message)

        def _on_diff_completed(results):
            btn_analyze.setEnabled(True)
            self.diff_worker = None
            _render_diff_results(results)

        def _on_diff_failed(message):
            btn_analyze.setEnabled(True)
            self.diff_worker = None
            lbl_summary.setText(f"분석 실패: {message}")

        def run_analysis():
            if self.diff_worker and self.diff_worker.isRunning():
                return
            lbl_summary.setText("분석 중...")
            btn_analyze.setEnabled(False)
            self.diff_worker = DiffAnalyzeWorker(list(self.config.items), self.browser, self.diff_analyzer)
            self.diff_worker.progress.connect(_on_diff_progress)
            self.diff_worker.completed.connect(_on_diff_completed)
            self.diff_worker.failed.connect(_on_diff_failed)
            self.diff_worker.start()

        btn_analyze.clicked.connect(run_analysis)

        dialog.finished.connect(
            lambda _=None: (
                self.diff_worker.cancel() if self.diff_worker and self.diff_worker.isRunning() else None
            )
        )

        # 닫기 버튼
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(dialog.reject)
        layout.addWidget(btn_close)

        dialog.exec()
