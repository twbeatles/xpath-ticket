# -*- coding: utf-8 -*-
"""XPath Explorer mixin module (auto-split from legacy main file)."""

import csv
import json
import os
import random
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit, QComboBox, QCheckBox,
    QTableWidget, QTableWidgetItem, QTabWidget, QSplitter, QGroupBox,
    QProgressBar, QMenu, QToolBar, QDialog, QDialogButtonBox,
    QListWidget, QListWidgetItem, QMessageBox, QFileDialog, QHeaderView,
    QAbstractItemView, QSpinBox, QFormLayout, QScrollArea, QFrame, QTableView,
    QTreeWidget, QTreeWidgetItem, QPlainTextEdit, QStackedWidget, QMenuBar,
    QToolButton, QGridLayout, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize, QSettings, QPropertyAnimation, QEasingCurve, QMimeData
from PyQt6.QtGui import QFont, QColor, QAction, QPalette, QIcon, QPixmap, QKeySequence, QDrag

from xpath_explorer.core.constants import (
    APP_TITLE,
    APP_VERSION,
    SITE_PRESETS,
    BROWSER_CHECK_INTERVAL,
    SEARCH_DEBOUNCE_MS,
    LIVE_PREVIEW_DEBOUNCE_MS,
    WORKER_WAIT_TIMEOUT,
    category_to_label,
)
from xpath_explorer.ui.styles import STYLE
from xpath_explorer.core.config import XPathItem, SiteConfig
from xpath_explorer.ui.widgets import (
    ToastWidget,
    NoWheelComboBox,
    AnimatedStatusIndicator,
    IconButton,
    CollapsibleBox,
)
from xpath_explorer.browser.browser import BrowserManager
from xpath_explorer.workers.background import (
    PickerWatcher,
    ValidateWorker,
    LivePreviewWorker,
    AIGenerateWorker,
    DiffAnalyzeWorker,
    BatchTestWorker,
    BatchScenarioWorker,
)
from xpath_explorer.core.perf import perf_span, log_perf_summary
from xpath_explorer.tools.codegen import CodeGenerator, CodeTemplate, XPathTemplate
from xpath_explorer.analysis.statistics import StatisticsManager
from xpath_explorer.tools.optimizer import XPathOptimizer, XPathAlternative
from xpath_explorer.state.history import HistoryManager
from xpath_explorer.tools.ai import XPathAIAssistant
from xpath_explorer.analysis.diff import XPathDiffAnalyzer
from xpath_explorer.ui.table_model import XPathItemTableModel
from xpath_explorer.ui.filter_proxy import XPathFilterProxyModel
from xpath_explorer.browser.dom_export import (
    render_dom_report_htm,
    render_dom_diff_report_htm,
    diff_dom_snapshots,
)

from xpath_explorer.runtime import logger, error_telemetry


class ExplorerToolsMixin:
    def _batch_test(self, category: Optional[str] = None):
        """배치 테스트 실행 (취소 가능, 비동기)"""
        if not self.browser.is_alive():
            self._show_toast("브라우저를 먼저 연결해주세요.", "warning")
            return

        if self.batch_worker and self.batch_worker.isRunning():
            self._show_toast("이미 배치 테스트가 실행 중입니다.", "warning")
            return
        
        # 테스트할 항목 필터링
        items_to_test = self.config.items
        if category and category != "전체":
            items_to_test = [i for i in items_to_test if i.category == category]
        
        if not items_to_test:
            self._show_toast("테스트할 항목이 없습니다.", "warning")
            return
        
        self._show_toast(f"{len(items_to_test)}개 항목 배치 테스트 시작...", "info")

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("테스트 준비 중...")
        self.btn_open.setEnabled(False)  # 브라우저 버튼 비활성화
        self.batch_worker = BatchTestWorker(self.browser, list(items_to_test))
        self.batch_worker.progress.connect(self._on_batch_test_progress)
        self.batch_worker.item_tested.connect(self._on_batch_item_tested)
        self.batch_worker.completed.connect(self._on_batch_test_completed)
        self.batch_worker.start()

    def _on_batch_test_progress(self, value: int, message: str):
        self.progress_bar.setValue(value)
        self.progress_bar.setFormat(f"{message} - ESC로 취소")

    def _on_batch_item_tested(self, name: str, success: bool, xpath: str, msg: str):
        self._record_validation_outcome(
            name=name,
            xpath=xpath,
            success=success,
            result={
                'found': success,
                'msg': msg,
            },
        )

    def _on_batch_test_completed(self, results: list, cancelled: bool):
        self.progress_bar.setVisible(False)
        self.progress_bar.setFormat("%p%")
        self.btn_open.setEnabled(True)
        self.batch_worker = None
        self._refresh_table()
        if cancelled:
            self._show_toast("배치 테스트가 취소되었습니다.", "warning")
        if results:
            self._show_batch_report(results, cancelled=cancelled)

    def _batch_test_dialog(self):
        """카테고리 선택 후 배치 테스트"""
        categories = ["전체"] + sorted(self.config.get_categories())
        
        from PyQt6.QtWidgets import QInputDialog
        category, ok = QInputDialog.getItem(
            self, "배치 테스트", "테스트할 카테고리 선택:",
            categories, 0, False
        )
        if ok and category is not None:
            self._batch_test(category)

    @staticmethod
    def _default_scenario_json() -> str:
        sample = {
            "name": "기본 시나리오",
            "steps": [
                {"name": "로그인 ID 확인", "action": "validate_item", "item": "login_id"},
                {"name": "잠시 대기", "action": "wait", "seconds": 0.5},
                {"name": "예매 버튼 확인", "action": "validate_xpath", "xpath": "//a[contains(.,'예매하기')]"},
            ],
        }
        return json.dumps(sample, ensure_ascii=False, indent=2)

    def _show_batch_scenario_runner(self):
        """JSON 시나리오 기반 배치 실행기."""
        if not self.browser.is_alive():
            self._show_toast("브라우저를 먼저 연결해주세요.", "warning")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("🧪 배치 시나리오 실행기")
        dialog.resize(980, 680)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(10)

        layout.addWidget(QLabel("시나리오 JSON"))
        input_json = QPlainTextEdit()
        input_json.setPlainText(self._default_scenario_json())
        input_json.setStyleSheet("font-family: 'Consolas', monospace;")
        input_json.setMinimumHeight(220)
        layout.addWidget(input_json)

        control_row = QHBoxLayout()
        btn_load = QPushButton("📂 JSON 불러오기")
        btn_save = QPushButton("💾 JSON 저장")
        btn_run = QPushButton("▶ 실행")
        btn_cancel = QPushButton("⏹ 취소")
        btn_cancel.setEnabled(False)
        control_row.addWidget(btn_load)
        control_row.addWidget(btn_save)
        control_row.addStretch()
        control_row.addWidget(btn_run)
        control_row.addWidget(btn_cancel)
        layout.addLayout(control_row)

        progress = QProgressBar()
        progress.setValue(0)
        layout.addWidget(progress)

        lbl_summary = QLabel("대기 중")
        lbl_summary.setStyleSheet("color: #6c7086;")
        layout.addWidget(lbl_summary)

        table = QTableWidget()
        table.setColumnCount(10)
        table.setHorizontalHeaderLabels(
            ["#", "이름", "액션", "대상", "결과", "메시지", "ms", "시도", "재시도", "최대시도"]
        )
        table_hh = table.horizontalHeader()
        if table_hh is not None:
            table_hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            table_hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            table_hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            table_hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
            table_hh.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
            table_hh.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
            table_hh.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
            table_hh.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
            table_hh.setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents)
            table_hh.setSectionResizeMode(9, QHeaderView.ResizeMode.ResizeToContents)
        table_vh = table.verticalHeader()
        if table_vh is not None:
            table_vh.setVisible(False)
        layout.addWidget(table, 1)

        worker: Optional[BatchScenarioWorker] = None

        def set_run_state(running: bool):
            btn_run.setEnabled(not running)
            btn_cancel.setEnabled(running)
            btn_load.setEnabled(not running)
            btn_save.setEnabled(not running)

        def append_step_row(row: Dict[str, Any]):
            r = table.rowCount()
            table.insertRow(r)
            table.setItem(r, 0, QTableWidgetItem(str(row.get("step", r + 1))))
            table.setItem(r, 1, QTableWidgetItem(str(row.get("name", ""))))
            table.setItem(r, 2, QTableWidgetItem(str(row.get("action", ""))))
            table.setItem(r, 3, QTableWidgetItem(str(row.get("target", ""))))

            success = bool(row.get("success"))
            status_item = QTableWidgetItem("✅" if success else "❌")
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(r, 4, status_item)
            table.setItem(r, 5, QTableWidgetItem(str(row.get("msg", ""))))
            table.setItem(r, 6, QTableWidgetItem(str(row.get("duration_ms", 0))))
            table.setItem(r, 7, QTableWidgetItem(str(row.get("attempt", 1))))
            table.setItem(r, 8, QTableWidgetItem(str(row.get("retry_count", 0))))
            table.setItem(r, 9, QTableWidgetItem(str(row.get("max_attempts", 1))))

            if row.get("action") in ("validate_item", "item"):
                item_name = str(row.get("item_name", "") or "")
                xpath = str(row.get("xpath", "") or "")
                if item_name and xpath and self.config.get_item(item_name):
                    self._record_validation_outcome(
                        name=item_name,
                        xpath=xpath,
                        success=success,
                        result={
                            "found": success,
                            "msg": row.get("msg", ""),
                            "frame_path": row.get("frame_path", ""),
                            "count": row.get("count", 0),
                        },
                    )

        def on_progress(value: int, message: str):
            progress.setValue(value)
            lbl_summary.setText(message)

        def on_failed(message: str):
            nonlocal worker
            worker = None
            self.scenario_worker = None
            set_run_state(False)
            reason = str(message or "알 수 없는 오류")
            lbl_summary.setText(f"실패: {reason}")
            self._show_toast(f"시나리오 실행 실패: {reason}", "error")

        def on_completed(results: list, cancelled: bool, scenario_name: str):
            nonlocal worker
            worker = None
            self.scenario_worker = None
            set_run_state(False)
            self._refresh_table()

            success_count = sum(1 for row in results if row.get("success"))
            total = len(results)
            success_rate = (success_count / total * 100.0) if total > 0 else 0.0
            total_retries = sum(max(0, int(row.get("retry_count", 0) or 0)) for row in results)
            toast_type, status_text = self._classify_scenario_result(success_count, total, cancelled)
            summary_text = (
                f"성공 {success_count}/{total} | 성공률 {success_rate:.1f}% | 총 재시도 {total_retries}"
            )
            lbl_summary.setText(f"{scenario_name} {status_text}: {summary_text}")
            self._show_toast(f"시나리오 {status_text}: {summary_text}", toast_type)
            if results:
                self._show_batch_report(
                    results,
                    cancelled=cancelled,
                    title=f"시나리오 결과 - {scenario_name}",
                    retry_total=total_retries,
                )

        def start_run():
            nonlocal worker
            if worker is not None and worker.isRunning():
                return

            if not self.browser.is_alive():
                self._show_toast("브라우저 연결이 끊어졌습니다.", "warning")
                return

            try:
                scenario = json.loads(input_json.toPlainText().strip() or "{}")
            except json.JSONDecodeError as e:
                self._show_toast(f"JSON 파싱 실패: {e}", "error")
                return

            if not isinstance(scenario, dict) or not isinstance(scenario.get("steps"), list):
                self._show_toast("시나리오 형식이 올바르지 않습니다. (steps 배열 필요)", "warning")
                return

            table.setRowCount(0)
            progress.setValue(0)
            lbl_summary.setText("시나리오 시작...")

            worker = BatchScenarioWorker(self.browser, list(self.config.items), scenario)
            self.scenario_worker = worker
            worker.progress.connect(on_progress)
            worker.step_completed.connect(append_step_row)
            worker.completed.connect(on_completed)
            worker.failed.connect(on_failed)
            set_run_state(True)
            worker.start()

        def cancel_run():
            if worker is not None and worker.isRunning():
                worker.cancel()

        def load_json_file():
            fname, _ = QFileDialog.getOpenFileName(
                dialog,
                "시나리오 JSON 불러오기",
                "",
                "JSON 파일 (*.json)",
            )
            if not fname:
                return
            try:
                with open(fname, "r", encoding="utf-8") as f:
                    input_json.setPlainText(f.read())
            except Exception as e:
                self._show_toast(f"시나리오 파일 로드 실패: {e}", "error")

        def save_json_file():
            fname, _ = QFileDialog.getSaveFileName(
                dialog,
                "시나리오 JSON 저장",
                "batch_scenario.json",
                "JSON 파일 (*.json)",
            )
            if not fname:
                return
            try:
                with open(fname, "w", encoding="utf-8") as f:
                    f.write(input_json.toPlainText())
                self._show_toast(f"시나리오 저장 완료: {fname}", "success")
            except Exception as e:
                self._show_toast(f"시나리오 저장 실패: {e}", "error")

        btn_run.clicked.connect(start_run)
        btn_cancel.clicked.connect(cancel_run)
        btn_load.clicked.connect(load_json_file)
        btn_save.clicked.connect(save_json_file)

        def on_dialog_close():
            if worker is not None and worker.isRunning():
                worker.cancel()
                worker.wait(WORKER_WAIT_TIMEOUT)
            self.scenario_worker = None

        dialog.finished.connect(lambda _=None: on_dialog_close())
        dialog.exec()

    def _classify_scenario_result(self, success_count: int, total: int, cancelled: bool) -> Tuple[str, str]:
        if cancelled:
            return ("warning", "취소됨")
        if total <= 0:
            return ("warning", "완료(실행 결과 없음)")

        success_rate = (float(success_count) / float(total)) * 100.0
        if success_rate >= 100.0:
            return ("success", "완료")
        if success_rate >= 80.0:
            return ("warning", "완료(일부 경고)")
        return ("error", "완료(실패 다수)")

    @staticmethod
    def _top_failure_reasons(results: List[Dict[str, Any]], top_n: int = 5) -> List[Tuple[str, int]]:
        counter: Counter[str] = Counter()
        for row in results:
            if bool(row.get("success")):
                continue
            reason = str(row.get("msg", "") or "Unknown error").strip() or "Unknown error"
            counter[reason] += 1
        return list(counter.most_common(max(1, int(top_n))))

    def _show_batch_report(
        self,
        results: list,
        cancelled: bool = False,
        title: str = "배치 테스트 결과",
        retry_total: Optional[int] = None,
    ):
        """배치/시나리오 결과 리포트."""
        dialog = QDialog(self)
        window_title = title + (" (취소됨)" if cancelled else "")
        dialog.setWindowTitle(window_title)
        dialog.resize(760, 620)

        layout = QVBoxLayout(dialog)

        total = len(results)
        success_count = sum(1 for r in results if bool(r.get("success")))
        success_rate = (success_count / total * 100.0) if total > 0 else 0.0
        if retry_total is None:
            retry_total = sum(max(0, int(r.get("retry_count", 0) or 0)) for r in results)

        cancelled_text = " | 상태: 취소됨" if cancelled else ""
        summary = QLabel(
            f"총 {total}개 | 성공 {success_count} | 실패 {total - success_count} | "
            f"성공률 {success_rate:.1f}% | 총 재시도 {retry_total}{cancelled_text}"
        )
        summary.setStyleSheet("font-size: 15px; font-weight: bold; padding: 8px;")
        layout.addWidget(summary)

        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["상태", "이름", "결과"])
        batch_hh = table.horizontalHeader()
        if batch_hh is not None:
            batch_hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            batch_hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            batch_hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        for r in results:
            row = table.rowCount()
            table.insertRow(row)
            success = bool(r.get("success"))
            status = QTableWidgetItem("✅" if success else "❌")
            status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, 0, status)
            table.setItem(row, 1, QTableWidgetItem(str(r.get("name", r.get("item_name", "-")))))
            table.setItem(row, 2, QTableWidgetItem(str(r.get("msg", "Found" if success else "Not found"))))

        layout.addWidget(table)

        top_failures = self._top_failure_reasons(results, top_n=5)
        if top_failures:
            layout.addWidget(QLabel("Top 실패 원인"))
            txt_failures = QPlainTextEdit()
            txt_failures.setReadOnly(True)
            txt_failures.setMaximumHeight(120)
            txt_failures.setPlainText(
                "\n".join(f"{idx}. {reason} ({count}회)" for idx, (reason, count) in enumerate(top_failures, start=1))
            )
            layout.addWidget(txt_failures)

        telemetry_summary = error_telemetry.get_summary(top_n=5)
        layout.addWidget(QLabel("에러 텔레메트리 요약"))
        txt_telemetry = QPlainTextEdit()
        txt_telemetry.setReadOnly(True)
        txt_telemetry.setMaximumHeight(140)
        top_errors = telemetry_summary.get("top_errors", [])
        telemetry_lines = [
            f"총 에러: {telemetry_summary.get('total_errors', 0)}",
            f"치명적 에러: {telemetry_summary.get('critical_count', 0)}",
            f"최근 버퍼 이벤트: {telemetry_summary.get('buffered_events', 0)}",
        ]
        if top_errors:
            telemetry_lines.append("")
            telemetry_lines.append("Top Error Types:")
            for idx, row in enumerate(top_errors, start=1):
                telemetry_lines.append(
                    f"{idx}. {row.get('module', '?')}.{row.get('function', '?')} - "
                    f"{row.get('message', '')} ({row.get('count', 0)}회)"
                )
        txt_telemetry.setPlainText("\n".join(telemetry_lines))
        layout.addWidget(txt_telemetry)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_box.rejected.connect(dialog.reject)
        layout.addWidget(btn_box)

        dialog.exec()

    def _show_macro_generator(self):
        """매크로 생성 다이얼로그"""
        if not self.config.items:
            self._show_toast("생성할 XPath 항목이 없습니다.", "warning")
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("매크로 코드 생성")
        dialog.resize(800, 600)
        
        layout = QVBoxLayout(dialog)
        
        # 템플릿 선택
        layout.addWidget(QLabel("코드 템플릿:"))
        combo_template = QComboBox()
        combo_template.addItems(["Selenium (파이썬)", "Playwright (파이썬)", "PyAutoGUI"])
        layout.addWidget(combo_template)
        
        # 코드 미리보기
        layout.addWidget(QLabel("생성된 코드:"))
        txt_code = QPlainTextEdit()
        txt_code.setReadOnly(True)
        txt_code.setStyleSheet("font-family: 'Consolas', monospace; background-color: #181825;")
        layout.addWidget(txt_code)
        
        def generate_code():
            template_map = {
                0: CodeTemplate.SELENIUM_PYTHON,
                1: CodeTemplate.PLAYWRIGHT_PYTHON,
                2: CodeTemplate.PYAUTOGUI
            }
            template = template_map.get(combo_template.currentIndex(), CodeTemplate.SELENIUM_PYTHON)
            try:
                code = self.code_generator.generate(self.config.items, template)
            except Exception as e:
                txt_code.setPlainText(f"# 코드 생성 실패\n# {e}")
                self._show_toast(f"코드 생성 실패: {e}", "error")
                return
            txt_code.setPlainText(code)
        
        combo_template.currentIndexChanged.connect(generate_code)
        generate_code()  # 초기 생성
        
        # 버튼
        btn_layout = QHBoxLayout()
        
        btn_copy = QPushButton("📋 복사")
        def copy_code():
            clipboard = QApplication.clipboard()
            if clipboard is not None:
                clipboard.setText(txt_code.toPlainText())
            self._show_toast("코드가 클립보드에 복사되었습니다.", "success")
        btn_copy.clicked.connect(copy_code)
        btn_layout.addWidget(btn_copy)
        
        btn_save = QPushButton("💾 파일로 저장")
        def save_code():
            ext = ".py" if combo_template.currentIndex() < 2 else ".py"
            fname, _ = QFileDialog.getSaveFileName(dialog, "코드 저장", "macro_script", "파이썬 파일 (*.py)")
            if fname:
                with open(fname, 'w', encoding='utf-8') as f:
                    f.write(txt_code.toPlainText())
                self._show_toast(f"저장 완료: {fname}", "success")
        btn_save.clicked.connect(save_code)
        btn_layout.addWidget(btn_save)
        
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(dialog.reject)
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)
        dialog.exec()

    def _show_xpath_template_library(self):
        """XPath 템플릿 라이브러리 다이얼로그."""
        dialog = QDialog(self)
        dialog.setWindowTitle("📚 XPath 템플릿 라이브러리")
        dialog.resize(920, 620)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("카테고리:"))
        combo_category = QComboBox()
        combo_category.addItem("전체", "")
        for category in sorted({t.category for t in self.code_generator.list_xpath_templates()}):
            combo_category.addItem(category_to_label(category), category)
        filter_row.addWidget(combo_category)

        filter_row.addWidget(QLabel("검색:"))
        input_keyword = QLineEdit()
        input_keyword.setPlaceholderText("템플릿명, XPath, 설명 검색")
        filter_row.addWidget(input_keyword, 1)
        layout.addLayout(filter_row)

        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["카테고리", "템플릿명", "XPath", "설명", "사용"])
        table_hh = table.horizontalHeader()
        if table_hh is not None:
            table_hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            table_hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            table_hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
            table_hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
            table_hh.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        table_vh = table.verticalHeader()
        if table_vh is not None:
            table_vh.setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        layout.addWidget(table, 1)

        lbl_summary = QLabel("")
        lbl_summary.setStyleSheet("color: #6c7086;")
        layout.addWidget(lbl_summary)

        current_rows: List[XPathTemplate] = []

        def apply_template(template: XPathTemplate):
            self.input_xpath.setPlainText(template.xpath)
            if not self.input_desc.text().strip():
                self.input_desc.setText(template.description)
            if not self.input_name.text().strip():
                self.input_name.setText(template.name.replace(" ", "_"))
            if hasattr(self, "right_tabs") and self.right_tabs is not None:
                self.right_tabs.setCurrentIndex(0)
            self._show_toast(f"템플릿 적용: {template.name}", "success")
            dialog.accept()

        def refresh_table():
            nonlocal current_rows
            keyword = input_keyword.text().strip()
            category = str(combo_category.currentData() or "")
            current_rows = self.code_generator.list_xpath_templates(
                category=category,
                keyword=keyword,
            )

            table.setRowCount(len(current_rows))
            for row, template in enumerate(current_rows):
                table.setItem(row, 0, QTableWidgetItem(category_to_label(template.category)))
                table.setItem(row, 1, QTableWidgetItem(template.name))

                xpath_item = QTableWidgetItem(template.xpath)
                xpath_item.setToolTip(template.xpath)
                table.setItem(row, 2, xpath_item)
                table.setItem(row, 3, QTableWidgetItem(template.description))

                btn_apply = QPushButton("적용")
                btn_apply.setObjectName("success")
                btn_apply.setCursor(Qt.CursorShape.PointingHandCursor)
                btn_apply.clicked.connect(lambda _checked=False, t=template: apply_template(t))
                table.setCellWidget(row, 4, btn_apply)

            lbl_summary.setText(f"템플릿 {len(current_rows)}개")

        def on_double_click(row: int, _column: int):
            if 0 <= row < len(current_rows):
                apply_template(current_rows[row])

        table.cellDoubleClicked.connect(on_double_click)
        combo_category.currentIndexChanged.connect(lambda _=None: refresh_table())
        input_keyword.textChanged.connect(lambda _=None: refresh_table())
        refresh_table()

        btn_row = QHBoxLayout()
        btn_copy = QPushButton("📋 선택 XPath 복사")
        btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_row.addWidget(btn_copy)

        def copy_selected():
            row = table.currentRow()
            if row < 0 or row >= len(current_rows):
                self._show_toast("복사할 템플릿을 선택하세요.", "warning")
                return
            clipboard = QApplication.clipboard()
            if clipboard is not None:
                clipboard.setText(current_rows[row].xpath)
            self._show_toast("XPath가 클립보드에 복사되었습니다.", "success")

        btn_copy.clicked.connect(copy_selected)

        btn_row.addStretch()
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(dialog.reject)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

        dialog.exec()

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

    def _collect_active_dom_snapshots(self) -> Tuple[List[Any], str]:
        """현재 활성 브라우저(Selenium/Playwright)의 DOM 스냅샷 수집."""
        if self.browser.is_alive():
            return self.browser.collect_dom_snapshots(include_frames=True), "Selenium"
        if self.pw_manager and self.pw_manager.is_alive():
            return self.pw_manager.collect_dom_snapshots(include_frames=True), "Playwright"
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
            cast(QWidget, self),
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
                cast(QWidget, self),
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

    def _toggle_playwright(self):
        """Playwright 브라우저 토글"""
        try:
            from xpath_explorer.browser.playwright import PlaywrightManager
            
            if self.pw_manager is None:
                self.pw_manager = PlaywrightManager()
            
            if self.pw_manager.is_alive():
                self.pw_manager.close()
                self.lbl_pw_status.setText("● 미연결")
                self.lbl_pw_status.setStyleSheet("color: #f38ba8;")
                self.btn_pw_toggle.setText("Playwright 시작")
                self._show_toast("Playwright 브라우저가 종료되었습니다.", "info")
            else:
                url = self.input_url.text().strip() or "about:blank"
                if self.pw_manager.launch(headless=False, stealth=True):
                    if url != "about:blank":
                        self.pw_manager.navigate(url)
                    self.lbl_pw_status.setText("● 연결됨")
                    self.lbl_pw_status.setStyleSheet("color: #a6e3a1;")
                    self.btn_pw_toggle.setText("Playwright 종료")
                    self._show_toast("Playwright 브라우저가 시작되었습니다.", "success")
                else:
                    last_error = getattr(self.pw_manager, "last_error", "")
                    if last_error:
                        self._show_toast(f"Playwright 시작 실패: {last_error}", "error")
                    # EXE 환경에서도 사용 가능하도록 Chromium 설치 UX 제공
                    choice = QMessageBox.question(
                        self,
                        "Playwright 시작 실패",
                        "Playwright Chromium이 설치되지 않았거나 실행에 실패했습니다.\n\n"
                        "Chromium을 지금 설치하시겠습니까? (playwright install chromium)",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    if choice == QMessageBox.StandardButton.Yes:
                        self._show_toast("Chromium 설치 중... (잠시 기다려주세요)", "info", 4000)
                        ok = PlaywrightManager.install_chromium()
                        if ok and self.pw_manager.launch(headless=False, stealth=True):
                            if url != "about:blank":
                                self.pw_manager.navigate(url)
                            self.lbl_pw_status.setText("● 연결됨")
                            self.lbl_pw_status.setStyleSheet("color: #a6e3a1;")
                            self.btn_pw_toggle.setText("Playwright 종료")
                            self._show_toast("Playwright 브라우저가 시작되었습니다.", "success")
                        else:
                            self._show_toast("Chromium 설치/시작 실패. 콘솔 로그를 확인하세요.", "error")
                    else:
                        self._show_toast("Playwright 시작 실패", "error")
        except ImportError:
            self._show_toast("Playwright가 설치되지 않았습니다. pip install playwright", "error")
        except Exception as e:
            self._show_toast(f"Playwright 오류: {e}", "error")

    def _scan_page_elements(self):
        """Playwright로 페이지 요소 자동 스캔"""
        if not self.pw_manager or not self.pw_manager.is_alive():
            self._show_toast("Playwright 브라우저가 실행되지 않았습니다.", "warning")
            return
        
        scan_label = self.combo_scan_type.currentText()
        scan_type = self.combo_scan_type.currentData()
        if not isinstance(scan_type, str) or not scan_type:
            scan_type = scan_label
        self._show_toast(f"{scan_label} 스캔 중...", "info", 2000)
        
        try:
            with perf_span("ui.scan_page_elements"):
                elements = self.pw_manager.scan_elements(scan_type, max_count=50)
                
                self.table_scan_results.setUpdatesEnabled(False)
                self.table_scan_results.setRowCount(len(elements))
                
                for row, elem in enumerate(elements):
                    xpath = elem.xpath
                    if len(xpath) > 80:
                        xpath = xpath[:77] + "..."
                    self.table_scan_results.setItem(row, 0, QTableWidgetItem(xpath))
                    self.table_scan_results.setItem(row, 1, QTableWidgetItem(elem.tag))
                    text = elem.text[:30] + "..." if len(elem.text) > 30 else elem.text
                    self.table_scan_results.setItem(row, 2, QTableWidgetItem(text))
                    
                    btn_use = QPushButton("사용")
                    btn_use.setObjectName("success")
                    btn_use.setCursor(Qt.CursorShape.PointingHandCursor)
                    btn_use.clicked.connect(lambda checked, e=elem: self._use_scanned_element(e))
                    self.table_scan_results.setCellWidget(row, 3, btn_use)

                self.table_scan_results.setUpdatesEnabled(True)
                self.lbl_scan_summary.setText(f"스캔된 요소: {len(elements)}개")
                self._show_toast(f"{len(elements)}개의 {scan_label}를 찾았습니다.", "success")
            
        except Exception as e:
            self.table_scan_results.setUpdatesEnabled(True)
            self._show_toast(f"스캔 실패: {e}", "error")

    def _export_dom_playwright_htm(self):
        """현재 Playwright 브라우저의 전체 DOM을 단일 HTM으로 저장."""
        if not self.pw_manager or not self.pw_manager.is_alive():
            self._show_toast("Playwright 브라우저를 먼저 실행하세요.", "warning")
            return

        default_name = f"playwright_dom_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.htm"
        fname, _ = QFileDialog.getSaveFileName(
            cast(QWidget, self),
            "Playwright DOM 저장",
            default_name,
            "HTM 파일 (*.htm *.html)",
        )
        if not fname:
            return

        if not fname.lower().endswith((".htm", ".html")):
            fname += ".htm"

        self._show_toast("Playwright DOM 추출 중...", "info", 2000)
        try:
            snapshots = self.pw_manager.collect_dom_snapshots(include_frames=True)
            report = render_dom_report_htm(snapshots, source_label="Playwright")
            with open(fname, "w", encoding="utf-8") as f:
                f.write(report)

            fail_count = sum(1 for s in snapshots if s.error)
            self._show_toast(
                f"DOM 저장 완료: {fname} (문서 {len(snapshots)}개, 실패 {fail_count}개)",
                "success",
                5000,
            )
        except Exception as e:
            logger.error(f"Playwright DOM 저장 실패: {e}")
            self._show_toast(f"DOM 저장 실패: {e}", "error")

    def _use_scanned_element(self, element):
        """스캔된 요소를 편집기로 로드"""
        self.input_xpath.setPlainText(element.xpath)
        self.input_css.setText(element.css_selector)
        
        # 자동 이름 생성 (태그 + ID 또는 이름)
        if element.element_id:
            suggested_name = element.element_id
        elif element.element_name:
            suggested_name = element.element_name
        else:
            suggested_name = f"{element.tag}_{len(self.config.items) + 1}"
        
        self.input_name.setText(suggested_name)
        self.input_desc.setText(element.text[:50] if element.text else "")
        
        self._show_toast(f"'{suggested_name}' 요소를 로드했습니다.", "success")
        
        # Playwright에서 하이라이트
        if self.pw_manager and self.pw_manager.is_alive():
            self.pw_manager.highlight(element.xpath, 2000)

    def _reset_history_baseline(self):
        """현재 항목 목록을 Undo/Redo 기준 상태로 재설정."""
        self.history_manager.initialize(self.config.items)
        self._update_undo_redo_actions()

    def _update_undo_redo_actions(self):
        """Undo/Redo 액션 상태 업데이트"""
        if self.undo_action is None or self.redo_action is None:
            return
        self.undo_action.setEnabled(self.history_manager.can_undo())
        self.redo_action.setEnabled(self.history_manager.can_redo())
        
        if self.history_manager.can_undo():
            self.undo_action.setText(f"↩️ 실행 취소 ({self.history_manager.get_undo_description()})")
        else:
            self.undo_action.setText("↩️ 실행 취소")

    def _undo(self):
        """실행 취소"""
        restored = self.history_manager.undo()
        if restored is not None:
            self._restore_items_from_dicts(restored)
            self._filter_options_dirty = True
            self._refresh_table(refresh_filters=True)
            self._update_undo_redo_actions()
            self._show_toast("실행 취소됨", "info")

    def _redo(self):
        """다시 실행"""
        restored = self.history_manager.redo()
        if restored is not None:
            self._restore_items_from_dicts(restored)
            self._filter_options_dirty = True
            self._refresh_table(refresh_filters=True)
            self._update_undo_redo_actions()
            self._show_toast("다시 실행됨", "info")

    def _restore_items_from_dicts(self, item_dicts: list):
        """딕셔너리 리스트에서 XPathItem 복원"""
        restored_items = []
        for d in item_dicts:
            item = XPathItem(
                name=d.get('name', ''),
                xpath=d.get('xpath', ''),
                category=d.get('category', 'common'),
                description=d.get('description', ''),
                css_selector=d.get('css_selector', ''),
                is_verified=d.get('is_verified', False),
                element_tag=d.get('element_tag', ''),
                element_text=d.get('element_text', ''),
                found_window=d.get('found_window', ''),
                found_frame=d.get('found_frame', ''),
                is_favorite=d.get('is_favorite', False),
                tags=d.get('tags', []),
                test_count=d.get('test_count', 0),
                success_count=d.get('success_count', 0),
                last_tested=d.get('last_tested', ''),
                sort_order=d.get('sort_order', 0),
                alternatives=d.get('alternatives', []),
                element_attributes=d.get('element_attributes', {}),
                screenshot_path=d.get('screenshot_path', ''),
                ai_generated=d.get('ai_generated', False)
            )
            restored_items.append(item)
        self.config.replace_items(restored_items)
        self._table_data_dirty = True

    def _save_item_with_history(self):
        """항목 저장 (히스토리 기록 포함)"""
        name = self.input_name.text().strip()
        existing = self.config.get_item(name)
        action = "update" if existing else "add"
        
        # 변경 전 상태 저장
        self.history_manager.push_state(
            self.config.items, action, name,
            f"{name} 항목 {'수정' if existing else '추가'}"
        )
        
        # 원래 저장 로직은 _save_item()에서 처리
        self._update_undo_redo_actions()

    def _show_xpath_alternatives(self):
        """XPath 대안 제안 다이얼로그"""
        xpath = self.input_xpath.toPlainText().strip()
        
        if not xpath:
            self._show_toast("XPath를 먼저 입력하세요.", "warning")
            return
        
        if not self.browser.is_alive():
            self._show_toast("브라우저를 먼저 연결하세요.", "warning")
            return
        
        # 요소 정보 가져오기
        element_info = self.browser.get_element_info(xpath)
        
        if not element_info or not element_info.get('found'):
            self._show_toast("요소를 찾을 수 없습니다.", "error")
            return
        
        # 대안 생성
        element_info['original_xpath'] = xpath
        alternatives = self.optimizer.generate_alternatives(element_info)
        
        if not alternatives:
            self._show_toast("대안을 생성할 수 없습니다.", "warning")
            return
        
        # 다이얼로그 표시
        dialog = QDialog(self)
        dialog.setWindowTitle("💡 XPath 대안 제안")
        dialog.resize(700, 500)
        
        layout = QVBoxLayout(dialog)
        
        # 요소 정보 요약
        info_text = f"요소: <{element_info.get('tag', '?')}>"
        if element_info.get('id'):
            info_text += f" id='{element_info['id']}'"
        if element_info.get('class'):
            info_text += f" class='{element_info['class'][:30]}...'" if len(element_info.get('class', '')) > 30 else f" class='{element_info.get('class', '')}'"
        
        lbl_info = QLabel(info_text)
        lbl_info.setWordWrap(True)
        lbl_info.setStyleSheet("color: #89b4fa; padding: 5px;")
        layout.addWidget(lbl_info)
        
        # 대안 테이블
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["점수", "전략", "XPath", "사용"])
        alt_hh = table.horizontalHeader()
        if alt_hh is not None:
            alt_hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        table.setColumnWidth(0, 50)
        table.setColumnWidth(1, 100)
        table.setColumnWidth(3, 60)
        alt_vh = table.verticalHeader()
        if alt_vh is not None:
            alt_vh.setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        
        for alt in alternatives:
            row = table.rowCount()
            table.insertRow(row)
            
            # 점수
            score_item = QTableWidgetItem(f"{alt.robustness_score:.0f}")
            score_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if alt.robustness_score >= 80:
                score_item.setForeground(QColor("#a6e3a1"))
            elif alt.robustness_score >= 50:
                score_item.setForeground(QColor("#fab387"))
            else:
                score_item.setForeground(QColor("#f38ba8"))
            table.setItem(row, 0, score_item)
            
            # 전략
            table.setItem(row, 1, QTableWidgetItem(alt.strategy))
            
            # XPath
            xpath_item = QTableWidgetItem(alt.xpath)
            xpath_item.setToolTip(alt.description)
            table.setItem(row, 2, xpath_item)
            
            # 사용 버튼
            btn_use = QPushButton("사용")
            btn_use.setObjectName("success")
            btn_use.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_use.clicked.connect(lambda checked, x=alt.xpath: (
                self.input_xpath.setPlainText(x),
                self._show_toast("XPath 적용됨", "success"),
                dialog.accept()
            ))
            table.setCellWidget(row, 3, btn_use)
        
        layout.addWidget(table)
        
        # 닫기 버튼
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(dialog.reject)
        layout.addWidget(btn_close)
        
        dialog.exec()

    def _show_ai_assistant(self):
        """AI XPath 추천 다이얼로그"""
        dialog = QDialog(self)
        dialog.setWindowTitle("🤖 AI XPath 추천")
        dialog.resize(600, 450)
        
        layout = QVBoxLayout(dialog)
        
        # API 상태
        if self.ai_assistant.is_available():
            provider = (self.ai_assistant._provider or "openai").capitalize()
            status_text = f"✅ {provider} API 연결됨"
            status_color = "#a6e3a1"
        else:
            status_text = "⚠️ API 키 미설정 (규칙 기반 모드)"
            status_color = "#fab387"
        
        lbl_status = QLabel(status_text)
        lbl_status.setStyleSheet(f"color: {status_color}; font-weight: bold;")
        layout.addWidget(lbl_status)
        
        # 입력
        layout.addWidget(QLabel("찾고자 하는 요소를 설명하세요:"))
        self._ai_input = QPlainTextEdit()
        self._ai_input.setMaximumHeight(80)
        self._ai_input.setPlaceholderText("예: 로그인 버튼, 이메일 입력창, 예매하기 링크...")
        layout.addWidget(self._ai_input)
        
        # 생성 버튼
        btn_generate = QPushButton("🔮 XPath 생성")
        btn_generate.setObjectName("primary")
        btn_generate.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(btn_generate)
        
        # 결과 영역
        layout.addWidget(QLabel("추천 결과:"))
        self._ai_result_text = QPlainTextEdit()
        self._ai_result_text.setReadOnly(True)
        self._ai_result_text.setStyleSheet("font-family: 'Consolas', monospace; background-color: #181825;")
        layout.addWidget(self._ai_result_text)
        
        # 신뢰도 라벨
        self._ai_confidence_label = QLabel("")
        layout.addWidget(self._ai_confidence_label)

        def _apply_ai_result(result):
            self._ai_last_xpath = result.xpath or ""
            output = f"추천 XPath:\n{result.xpath}\n\n"
            if result.alternative_xpaths:
                output += "대안:\n" + "\n".join(f"  - {x}" for x in result.alternative_xpaths) + "\n\n"
            output += f"설명:\n{result.explanation}"
            self._ai_result_text.setPlainText(output)
            
            conf = result.confidence * 100
            if conf >= 70:
                self._ai_confidence_label.setText(f"신뢰도: {conf:.0f}% (높음)")
                self._ai_confidence_label.setStyleSheet("color: #a6e3a1;")
            elif conf >= 40:
                self._ai_confidence_label.setText(f"신뢰도: {conf:.0f}% (보통)")
                self._ai_confidence_label.setStyleSheet("color: #fab387;")
            else:
                self._ai_confidence_label.setText(f"신뢰도: {conf:.0f}% (낮음)")
                self._ai_confidence_label.setStyleSheet("color: #f38ba8;")

        def _on_ai_generated(request_id: int, result):
            if request_id != self._ai_request_id:
                return
            _apply_ai_result(result)

        def _on_ai_failed(request_id: int, error: str):
            if request_id != self._ai_request_id:
                return
            self._ai_last_xpath = ""
            self._ai_result_text.setPlainText(f"생성 실패:\n{error}")
            self._ai_confidence_label.setText("")

        def _on_ai_worker_finished(worker):
            if self.ai_worker is worker:
                self.ai_worker = None
            btn_generate.setEnabled(True)
        
        def generate():
            with perf_span("ui.ai_generate_click"):
                desc = self._ai_input.toPlainText().strip()
                if not desc:
                    self._show_toast("설명을 입력하세요.", "warning")
                    return

                self._ai_request_id += 1
                request_id = self._ai_request_id

                if self.ai_worker and self.ai_worker.isRunning():
                    self.ai_worker.cancel()

                btn_generate.setEnabled(False)
                self._ai_last_xpath = ""
                self._ai_result_text.setPlainText("생성 중...")
                self._ai_confidence_label.setText("")

                worker = AIGenerateWorker(self.ai_assistant, desc, request_id)
                worker.generated.connect(_on_ai_generated)
                worker.failed.connect(_on_ai_failed)
                worker.finished.connect(lambda w=worker: _on_ai_worker_finished(w))
                self.ai_worker = worker
                worker.start()
        
        btn_generate.clicked.connect(generate)
        
        # 적용 버튼
        btn_layout = QHBoxLayout()
        
        btn_apply = QPushButton("📋 편집기에 적용")
        btn_apply.clicked.connect(lambda: (
            self.input_xpath.setPlainText(self._ai_last_xpath or ""),
            self._show_toast("XPath 적용됨", "success") if self._ai_last_xpath else self._show_toast("적용할 XPath가 없습니다.", "warning")
        ))
        btn_layout.addWidget(btn_apply)
        
        btn_settings = QPushButton("⚙️ API 설정")
        btn_settings.clicked.connect(lambda: self._configure_ai_api(dialog))
        btn_layout.addWidget(btn_settings)
        
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(dialog.reject)
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)
        dialog.finished.connect(
            lambda _=None: (
                self.ai_worker.cancel() if self.ai_worker and self.ai_worker.isRunning() else None
            )
        )
        dialog.exec()

    def _configure_ai_api(self, parent_dialog):
        """AI API 설정 (Provider 지원)"""
        dialog = QDialog(parent_dialog)
        dialog.setWindowTitle("⚙️ AI 설정")
        dialog.resize(400, 300)
        
        layout = QVBoxLayout(dialog)
        
        # Provider 선택
        layout.addWidget(QLabel("AI 제공자:"))
        combo_provider = QComboBox()
        combo_provider.addItems(["openai", "gemini"])
        combo_provider.setCurrentText(self.ai_assistant._provider)
        layout.addWidget(combo_provider)
        
        # API 키 입력
        layout.addWidget(QLabel("API 키:"))
        input_key = QLineEdit()
        input_key.setEchoMode(QLineEdit.EchoMode.Password)
        if self.ai_assistant._provider == "openai":
            input_key.setText(self.ai_assistant._config.get('openai_api_key', ''))
        else:
            input_key.setText(self.ai_assistant._config.get('gemini_api_key', ''))
        layout.addWidget(input_key)
        
        # Model 입력
        layout.addWidget(QLabel("모델:"))
        input_model = QLineEdit()
        input_model.setText(self.ai_assistant._model)
        layout.addWidget(input_model)
        
        # 힌트
        lbl_hint = QLabel("OpenAI 권장: gpt-4o-mini, gpt-4o\nGemini 권장: gemini-flash-latest, gemini-pro")
        lbl_hint.setStyleSheet("color: #7f849c; font-size: 11px;")
        layout.addWidget(lbl_hint)
        
        # Provider 변경 시 처리
        def on_provider_change(text):
            input_key.clear()
            if text == "openai":
                input_key.setText(self.ai_assistant._config.get('openai_api_key', ''))
                input_model.setText("gpt-4o-mini")
            else:
                input_key.setText(self.ai_assistant._config.get('gemini_api_key', ''))
                input_model.setText("gemini-flash-latest")
                
        combo_provider.currentTextChanged.connect(on_provider_change)
        
        # 버튼 레이아웃
        btn_layout = QHBoxLayout()
        
        btn_save = QPushButton("저장")
        btn_save.setObjectName("success")
        def save():
            provider = combo_provider.currentText()
            key = input_key.text().strip()
            model = input_model.text().strip()
            
            if not key:
                self._show_toast("API 키를 입력하세요.", "warning")
                return
                
            self.ai_assistant.configure(key, model, provider)
            self._show_toast(f"{provider} 설정이 저장되었습니다.", "success")
            dialog.accept()
            
        btn_save.clicked.connect(save)
        btn_layout.addWidget(btn_save)
        
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(dialog.reject)
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)
        
        dialog.exec()

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

    def keyPressEvent(self, a0):
        """키보드 이벤트 처리 - ESC로 배치 테스트 취소"""
        from PyQt6.QtCore import Qt
        if a0.key() == Qt.Key.Key_Escape:
            if self.batch_worker and self.batch_worker.isRunning():
                self.batch_worker.cancel()
        super().keyPressEvent(a0)

    def _save_settings(self):
        """UI 설정 저장."""
        if not hasattr(self, "settings") or self.settings is None:
            return

        self.settings.setValue("ui/font_size", int(getattr(self, "_font_size", 14)))

        right_tab_index = 0
        right_tabs = getattr(self, "right_tabs", None)
        if right_tabs is not None and hasattr(right_tabs, "currentIndex"):
            try:
                right_tab_index = int(right_tabs.currentIndex())
            except Exception:
                right_tab_index = 0
        self.settings.setValue("ui/right_tab_index", right_tab_index)

        url_panel_expanded = True
        url_collapsible = getattr(self, "url_collapsible", None)
        if url_collapsible is not None:
            url_panel_expanded = bool(getattr(url_collapsible, "_expanded", True))
        self.settings.setValue("ui/url_panel_expanded", url_panel_expanded)

        preset_name = ""
        combo_preset = getattr(self, "combo_preset", None)
        if combo_preset is not None and hasattr(combo_preset, "currentText"):
            try:
                preset_name = str(combo_preset.currentText() or "").strip()
            except Exception:
                preset_name = ""
        if not preset_name and hasattr(self, "config") and getattr(self, "config", None) is not None:
            preset_name = str(getattr(self.config, "name", "") or "").strip()
        if preset_name:
            self.settings.setValue("ui/last_preset", preset_name)

    def _stop_worker_thread(self, worker: Any, worker_name: str, timeout: int = WORKER_WAIT_TIMEOUT):
        if worker is None:
            return
        try:
            if not worker.isRunning():
                return
        except Exception:
            return

        try:
            cancel_fn = getattr(worker, "cancel", None)
            stop_fn = getattr(worker, "stop", None)
            if callable(cancel_fn):
                cancel_fn()
            elif callable(stop_fn):
                stop_fn()

            wait_fn = getattr(worker, "wait", None)
            if callable(wait_fn):
                waited = wait_fn(timeout)
                if waited is False:
                    logger.warning(f"{worker_name} 종료 대기 타임아웃")
        except Exception as e:
            logger.warning(f"{worker_name} 종료 중 예외: {e}")

    def closeEvent(self, a0):
        """종료 처리"""
        logger.info("앱 종료 시작...")

        try:
            check_timer = getattr(self, "check_timer", None)
            if check_timer is not None:
                check_timer.stop()

            if hasattr(self, "settings") and self.settings is not None:
                self.settings.setValue("geometry", self.saveGeometry())
            self._save_settings()

            self._stop_worker_thread(getattr(self, "picker_watcher", None), "PickerWatcher")
            self._stop_worker_thread(getattr(self, "validate_worker", None), "ValidateWorker")
            self._stop_worker_thread(getattr(self, "live_preview_worker", None), "LivePreviewWorker")
            self._stop_worker_thread(getattr(self, "ai_worker", None), "AIWorker")
            self._stop_worker_thread(getattr(self, "diff_worker", None), "DiffWorker")
            self._stop_worker_thread(getattr(self, "batch_worker", None), "BatchWorker")
            self._stop_worker_thread(getattr(self, "scenario_worker", None), "BatchScenarioWorker")

            pw_manager = getattr(self, "pw_manager", None)
            if pw_manager is not None:
                try:
                    pw_manager.close()
                except Exception as e:
                    logger.warning(f"Playwright 종료 실패(무시): {e}")

            stats_manager = getattr(self, "stats_manager", None)
            if stats_manager is not None:
                try:
                    stats_manager.shutdown(timeout=5.0)
                except Exception:
                    try:
                        stats_manager.save()
                    except Exception:
                        pass

            try:
                log_perf_summary()
            except Exception:
                pass

            browser = getattr(self, "browser", None)
            if browser is not None:
                try:
                    browser.close()
                except Exception as e:
                    logger.warning(f"브라우저 종료 실패(무시): {e}")
        finally:
            logger.info("앱 종료 완료")
            a0.accept()
