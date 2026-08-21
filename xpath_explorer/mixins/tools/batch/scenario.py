# -*- coding: utf-8 -*-
# pyright: reportAttributeAccessIssue=false, reportCallIssue=false, reportArgumentType=false
"""XPath Explorer mixin module (auto-split from legacy main file)."""

import csv
import io
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


class BatchScenarioMixin:
    @staticmethod
    def _default_scenario_json() -> str:
        sample = {
            "name": "기본 시나리오",
            "leave_context": False,
            "steps": [
                {"name": "로그인 ID 확인", "action": "validate_item", "item": "login_id"},
                {"name": "잠시 대기", "action": "wait", "seconds": 0.5},
                {"name": "예매 버튼 확인", "action": "validate_xpath", "xpath": "//a[contains(.,'예매하기')]"},
            ],
        }
        return json.dumps(sample, ensure_ascii=False, indent=2)

    def _show_batch_scenario_runner(self):
        """JSON 시나리오 기반 배치 실행기."""
        pw_alive = bool(getattr(self, "pw_manager", None) and self.pw_manager.is_alive())
        if not self.browser.is_alive() and not pw_alive:
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
                            "window_handle": row.get("window_handle", ""),
                            "window_title": row.get("window_title", ""),
                            "window_url": row.get("window_url", ""),
                            "tag": row.get("tag", ""),
                            "count": row.get("count", 0),
                            "error_type": row.get("error_type", ""),
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

            pw_alive = bool(getattr(self, "pw_manager", None) and self.pw_manager.is_alive())
            if not self.browser.is_alive() and not pw_alive:
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

            if self._abort_if_driver_busy("시나리오 실행"):
                return
            self._stop_live_preview_sync()
            worker = BatchScenarioWorker(
                self.browser,
                list(self.config.items),
                scenario,
                playwright=getattr(self, "pw_manager", None),
            )
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
