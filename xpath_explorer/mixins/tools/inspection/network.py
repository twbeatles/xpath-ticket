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


class NetworkInspectionMixin:
    def _show_network_analyzer(self):
        """네트워크 분석 다이얼로그"""
        try:
            from xpath_explorer.browser.playwright import NetworkAnalyzer
        except ImportError:
            self._show_toast("Playwright 모듈을 찾을 수 없습니다.", "error")
            return

        analyzer = NetworkAnalyzer()
        if not analyzer.is_playwright_available():
            QMessageBox.warning(
                self, "Playwright 필요",
                "네트워크 분석 기능을 사용하려면 Playwright가 필요합니다.\n\n"
                "설치 방법:\n"
                "pip install playwright\n"
                "playwright install chromium"
            )
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("🌐 네트워크 분석")
        dialog.resize(900, 600)

        layout = QVBoxLayout(dialog)

        # 상태 및 컨트롤
        ctrl_layout = QHBoxLayout()

        lbl_status = QLabel("● 대기 중")
        ctrl_layout.addWidget(lbl_status)

        input_url = QLineEdit()
        input_url.setPlaceholderText("분석할 URL 입력...")
        input_url.setText(self.config.url or "https://")
        ctrl_layout.addWidget(input_url, 2)

        btn_start = QPushButton("🚀 캡처 시작")
        btn_stop = QPushButton("⏹ 중지")
        btn_stop.setEnabled(False)

        ctrl_layout.addWidget(btn_start)
        ctrl_layout.addWidget(btn_stop)

        layout.addLayout(ctrl_layout)

        # 결과 테이블
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["Method", "Status", "Type", "Size", "URL"])
        network_hh = table.horizontalHeader()
        if network_hh is not None:
            network_hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(table)

        # 이벤트 핸들러
        def start_capture():
            url = input_url.text().strip()
            if not url:
                return

            lbl_status.setText("● 브라우저 시작 중...")

            if analyzer.start_browser(url, headless=False):
                analyzer.start_capture()
                lbl_status.setText("● 캡처 중... (페이지 조작 후 중지)")
                lbl_status.setStyleSheet("color: #a6e3a1;")
                btn_start.setEnabled(False)
                btn_stop.setEnabled(True)
            else:
                last_error = getattr(analyzer, "last_error", "")
                if last_error:
                    lbl_status.setText(f"● 시작 실패: {last_error}")
                    self._show_toast(f"네트워크 분석기 시작 실패: {last_error}", "error")
                else:
                    lbl_status.setText("● 시작 실패")
                lbl_status.setStyleSheet("color: #f38ba8;")

        def stop_capture():
            requests = analyzer.stop_capture()
            analyzer.close()

            lbl_status.setText(f"● 완료 ({len(requests)}개 요청)")
            lbl_status.setStyleSheet("color: #89b4fa;")
            btn_start.setEnabled(True)
            btn_stop.setEnabled(False)

            # 테이블 채우기
            table.setRowCount(0)
            for req in requests:
                row = table.rowCount()
                table.insertRow(row)
                table.setItem(row, 0, QTableWidgetItem(req.method))
                table.setItem(row, 1, QTableWidgetItem(str(req.status)))
                table.setItem(row, 2, QTableWidgetItem(req.resource_type))
                table.setItem(row, 3, QTableWidgetItem(f"{req.response_size}"))
                table.setItem(row, 4, QTableWidgetItem(req.url[:100]))

        btn_start.clicked.connect(start_capture)
        btn_stop.clicked.connect(stop_capture)

        # 닫기 시 정리
        def on_close():
            analyzer.close()
            dialog.reject()

        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(on_close)
        layout.addWidget(btn_close)

        dialog.exec()
