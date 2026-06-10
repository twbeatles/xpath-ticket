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


class TelemetryInspectionMixin:
    def _show_error_telemetry(self):
        """오류 텔레메트리 대시보드."""
        dialog = QDialog(self)
        dialog.setWindowTitle("🚨 오류 텔레메트리")
        dialog.resize(860, 560)

        layout = QVBoxLayout(dialog)

        lbl_summary = QLabel()
        lbl_summary.setStyleSheet("font-size: 14px; font-weight: bold; padding: 8px;")
        layout.addWidget(lbl_summary)

        tabs = QTabWidget()
        layout.addWidget(tabs, 1)

        tab_top = QWidget()
        top_layout = QVBoxLayout(tab_top)
        table_top = QTableWidget()
        table_top.setColumnCount(4)
        table_top.setHorizontalHeaderLabels(["횟수", "모듈", "함수", "메시지"])
        top_hh = table_top.horizontalHeader()
        if top_hh is not None:
            top_hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            top_hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            top_hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            top_hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        top_layout.addWidget(table_top)
        tabs.addTab(tab_top, "Top 오류")

        tab_recent = QWidget()
        recent_layout = QVBoxLayout(tab_recent)
        table_recent = QTableWidget()
        table_recent.setColumnCount(4)
        table_recent.setHorizontalHeaderLabels(["시간", "레벨", "위치", "메시지"])
        recent_hh = table_recent.horizontalHeader()
        if recent_hh is not None:
            recent_hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            recent_hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            recent_hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            recent_hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        recent_layout.addWidget(table_recent)
        tabs.addTab(tab_recent, "최근 이벤트")

        def refresh_view():
            summary = error_telemetry.get_summary(top_n=30)
            lbl_summary.setText(
                f"누적 오류: {summary['total_errors']}건 | "
                f"치명 오류: {summary['critical_count']}건 | "
                f"고유 오류 유형: {summary['unique_error_types']}개 | "
                f"버퍼 이벤트: {summary['buffered_events']}건"
            )

            table_top.setRowCount(0)
            for row_data in summary["top_errors"]:
                row = table_top.rowCount()
                table_top.insertRow(row)
                table_top.setItem(row, 0, QTableWidgetItem(str(row_data["count"])))
                table_top.setItem(row, 1, QTableWidgetItem(row_data["module"]))
                table_top.setItem(row, 2, QTableWidgetItem(row_data["function"]))
                table_top.setItem(row, 3, QTableWidgetItem(row_data["message"]))

            recent_events = error_telemetry.get_recent_events(limit=200)
            table_recent.setRowCount(0)
            for event in recent_events:
                row = table_recent.rowCount()
                table_recent.insertRow(row)
                location = f"{event.module}.{event.function}:{event.line}"
                table_recent.setItem(row, 0, QTableWidgetItem(event.timestamp_iso))
                table_recent.setItem(row, 1, QTableWidgetItem(event.level))
                table_recent.setItem(row, 2, QTableWidgetItem(location))
                table_recent.setItem(row, 3, QTableWidgetItem(event.message))

        refresh_view()

        btn_layout = QHBoxLayout()

        btn_save = QPushButton("💾 리포트 저장")

        def save_report():
            default_name = f"error_telemetry_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            fname, _ = QFileDialog.getSaveFileName(
                self,
                "오류 텔레메트리 리포트 저장",
                default_name,
                "Markdown 파일 (*.md)",
            )
            if not fname:
                return
            if not fname.lower().endswith(".md"):
                fname += ".md"
            try:
                content = error_telemetry.render_markdown_report(top_n=30, recent_limit=200)
                with open(fname, "w", encoding="utf-8") as f:
                    f.write(content)
                self._show_toast(f"오류 리포트 저장 완료: {fname}", "success")
            except Exception as e:
                logger.error(f"오류 리포트 저장 실패: {e}")
                self._show_toast(f"리포트 저장 실패: {e}", "error")

        btn_save.clicked.connect(save_report)
        btn_layout.addWidget(btn_save)

        btn_clear = QPushButton("🧹 텔레메트리 초기화")

        def clear_telemetry():
            choice = QMessageBox.question(
                dialog,
                "오류 텔레메트리 초기화",
                "수집된 오류 텔레메트리 데이터를 초기화하시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if choice != QMessageBox.StandardButton.Yes:
                return
            error_telemetry.clear()
            refresh_view()
            self._show_toast("오류 텔레메트리가 초기화되었습니다.", "success")

        btn_clear.clicked.connect(clear_telemetry)
        btn_layout.addWidget(btn_clear)

        btn_refresh = QPushButton("↻ 새로고침")
        btn_refresh.clicked.connect(refresh_view)
        btn_layout.addWidget(btn_refresh)

        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(dialog.reject)
        btn_layout.addWidget(btn_close)

        layout.addLayout(btn_layout)
        dialog.exec()
