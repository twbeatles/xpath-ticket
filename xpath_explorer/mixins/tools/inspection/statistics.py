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


class StatisticsInspectionMixin:
    def _show_statistics(self):
        """통계 대시보드"""
        dialog = QDialog(self)
        dialog.setWindowTitle("📈 테스트 통계")
        dialog.resize(700, 500)

        layout = QVBoxLayout(dialog)

        # 전체 요약
        summary = self.stats_manager.get_summary()
        summary_text = (
            f"총 항목: {summary['total_items']}개 | "
            f"총 테스트: {summary['total_tests']}회 | "
            f"평균 성공률: {summary['average_success_rate']:.1f}%"
        )
        lbl_summary = QLabel(summary_text)
        lbl_summary.setStyleSheet("font-size: 15px; font-weight: bold; padding: 10px;")
        layout.addWidget(lbl_summary)

        # 탭 위젯
        tabs = QTabWidget()

        # 탭 1: 항목별 통계
        tab_items = QWidget()
        tab_items_layout = QVBoxLayout(tab_items)

        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["이름", "총 테스트", "성공", "실패", "성공률"])
        stats_hh = table.horizontalHeader()
        if stats_hh is not None:
            stats_hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)

        for item in self.config.items:
            if item.test_count > 0:
                row = table.rowCount()
                table.insertRow(row)
                table.setItem(row, 0, QTableWidgetItem(item.name))
                table.setItem(row, 1, QTableWidgetItem(str(item.test_count)))
                table.setItem(row, 2, QTableWidgetItem(str(item.success_count)))
                table.setItem(row, 3, QTableWidgetItem(str(item.test_count - item.success_count)))

                rate_item = QTableWidgetItem(f"{item.success_rate:.0f}%")
                if item.success_rate >= 80:
                    rate_item.setForeground(QColor("#a6e3a1"))
                elif item.success_rate < 50:
                    rate_item.setForeground(QColor("#f38ba8"))
                table.setItem(row, 4, rate_item)

        tab_items_layout.addWidget(table)
        tabs.addTab(tab_items, "항목별 통계")

        # 탭 2: 불안정 항목
        tab_unstable = QWidget()
        tab_unstable_layout = QVBoxLayout(tab_unstable)

        unstable_items = self.stats_manager.get_unstable_items(80)
        if unstable_items:
            list_unstable = QListWidget()
            for stat in unstable_items:
                list_unstable.addItem(f"❌ {stat.name} - 성공률: {stat.success_rate:.0f}% ({stat.total_tests}회)")
            tab_unstable_layout.addWidget(list_unstable)
        else:
            tab_unstable_layout.addWidget(QLabel("불안정한 항목이 없습니다. 👍"))

        tabs.addTab(tab_unstable, "불안정 항목")

        layout.addWidget(tabs)

        # 버튼
        btn_layout = QHBoxLayout()

        btn_clear = QPushButton("🗑 통계 초기화")
        btn_clear.clicked.connect(lambda: (
            self.stats_manager.clear_statistics(),
            self._show_toast("통계가 초기화되었습니다.", "success"),
            dialog.reject()
        ))
        btn_layout.addWidget(btn_clear)

        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(dialog.reject)
        btn_layout.addWidget(btn_close)

        layout.addLayout(btn_layout)

        dialog.exec()

    def _show_validation_history_panel(self):
        """최근 검증 결과를 실시간으로 보여주는 히스토리 패널."""
        dialog = QDialog(self)
        dialog.setWindowTitle("🕒 실시간 검증 히스토리")
        dialog.resize(980, 580)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(10)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("상태:"))
        combo_status = QComboBox()
        combo_status.addItem("전체", "all")
        combo_status.addItem("성공만", "success")
        combo_status.addItem("실패만", "failed")
        filter_row.addWidget(combo_status)
        filter_row.addWidget(QLabel("이름 필터:"))
        input_name = QLineEdit()
        input_name.setPlaceholderText("항목명 포함 검색")
        filter_row.addWidget(input_name, 1)
        filter_row.addWidget(QLabel("최대"))
        spin_limit = QSpinBox()
        spin_limit.setMinimum(10)
        spin_limit.setMaximum(500)
        spin_limit.setSingleStep(10)
        spin_limit.setValue(50)
        filter_row.addWidget(spin_limit)
        filter_row.addWidget(QLabel("건"))
        layout.addLayout(filter_row)

        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(["시간", "항목", "XPath", "결과", "프레임", "메시지"])
        table_hh = table.horizontalHeader()
        if table_hh is not None:
            table_hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            table_hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            table_hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
            table_hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
            table_hh.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
            table_hh.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        table_vh = table.verticalHeader()
        if table_vh is not None:
            table_vh.setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(table, 1)

        lbl_summary = QLabel("")
        lbl_summary.setStyleSheet("color: #6c7086;")
        layout.addWidget(lbl_summary)

        def refresh_view():
            records = self.stats_manager.get_recent_history(limit=500)
            status_filter = str(combo_status.currentData() or "all")
            name_filter = input_name.text().strip().lower()
            limit = spin_limit.value()

            filtered = []
            for record in records:
                if status_filter == "success" and not record.success:
                    continue
                if status_filter == "failed" and record.success:
                    continue
                if name_filter and name_filter not in record.item_name.lower():
                    continue
                filtered.append(record)

            filtered = filtered[:limit]
            table.setRowCount(0)
            for record in filtered:
                row = table.rowCount()
                table.insertRow(row)
                table.setItem(row, 0, QTableWidgetItem(record.timestamp[:19]))
                table.setItem(row, 1, QTableWidgetItem(record.item_name))
                xpath_item = QTableWidgetItem(record.xpath)
                xpath_item.setToolTip(record.xpath)
                table.setItem(row, 2, xpath_item)
                status_item = QTableWidgetItem("✅" if record.success else "❌")
                status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row, 3, status_item)
                table.setItem(row, 4, QTableWidgetItem(record.frame_path or "main"))
                table.setItem(row, 5, QTableWidgetItem(record.error_msg or ("Found" if record.success else "")))

            success_count = sum(1 for r in filtered if r.success)
            fail_count = len(filtered) - success_count
            lbl_summary.setText(
                f"표시 {len(filtered)}건 | 성공 {success_count}건 | 실패 {fail_count}건"
            )

        timer = QTimer(dialog)
        timer.setInterval(1000)
        timer.timeout.connect(refresh_view)
        timer.start()

        combo_status.currentIndexChanged.connect(lambda _=None: refresh_view())
        input_name.textChanged.connect(lambda _=None: refresh_view())
        spin_limit.valueChanged.connect(lambda _=None: refresh_view())
        refresh_view()

        btn_row = QHBoxLayout()
        btn_refresh = QPushButton("↻ 새로고침")
        btn_refresh.clicked.connect(refresh_view)
        btn_row.addWidget(btn_refresh)
        btn_row.addStretch()
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(dialog.reject)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

        dialog.exec()
