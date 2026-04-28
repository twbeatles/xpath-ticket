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


class ExplorerBatchToolsMixin:
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
        if hasattr(self.batch_worker, "item_validated"):
            self.batch_worker.item_validated.connect(self._on_batch_item_validated)
        else:
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

    def _on_batch_item_validated(self, name: str, result: Dict[str, Any]):
        self._record_validation_outcome(
            name=name,
            xpath=str(result.get("xpath", "") or ""),
            success=bool(result.get("success")),
            result={
                "found": bool(result.get("success")),
                "msg": result.get("msg", ""),
                "frame_path": result.get("frame_path", ""),
                "window_handle": result.get("window_handle", ""),
                "window_title": result.get("window_title", ""),
                "window_url": result.get("window_url", ""),
                "tag": result.get("tag", ""),
                "count": result.get("count", 0),
                "error_type": result.get("error_type", ""),
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

    @staticmethod
    def _batch_export_columns() -> List[str]:
        return [
            "status",
            "step",
            "name",
            "action",
            "item_name",
            "xpath",
            "target",
            "frame_path",
            "window_handle",
            "window_title",
            "window_url",
            "tag",
            "count",
            "error_type",
            "msg",
            "duration_ms",
            "attempt",
            "max_attempts",
            "retry_count",
        ]

    @classmethod
    def _batch_export_row(cls, row: Dict[str, Any]) -> Dict[str, Any]:
        name = str(row.get("name", row.get("item_name", "")) or "")
        item_name = str(row.get("item_name", "") or "")
        return {
            "status": "success" if bool(row.get("success")) else "failure",
            "step": row.get("step", ""),
            "name": name or item_name,
            "action": row.get("action", ""),
            "item_name": item_name,
            "xpath": row.get("xpath", ""),
            "target": row.get("target", ""),
            "frame_path": row.get("frame_path", ""),
            "window_handle": row.get("window_handle", ""),
            "window_title": row.get("window_title", ""),
            "window_url": row.get("window_url", ""),
            "tag": row.get("tag", ""),
            "count": row.get("count", ""),
            "error_type": row.get("error_type", ""),
            "msg": row.get("msg", ""),
            "duration_ms": row.get("duration_ms", ""),
            "attempt": row.get("attempt", ""),
            "max_attempts": row.get("max_attempts", ""),
            "retry_count": row.get("retry_count", ""),
        }

    @classmethod
    def _batch_results_to_csv(cls, results: List[Dict[str, Any]]) -> str:
        output = io.StringIO(newline="")
        columns = cls._batch_export_columns()
        writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in results:
            writer.writerow(cls._batch_export_row(row))
        return output.getvalue()

    @staticmethod
    def _escape_markdown_cell(value: Any) -> str:
        text = str(value if value is not None else "")
        return text.replace("\\", "\\\\").replace("|", "\\|").replace("\r\n", "<br>").replace("\n", "<br>")

    @classmethod
    def _batch_results_to_markdown(
        cls,
        results: List[Dict[str, Any]],
        *,
        title: str = "배치 테스트 결과",
        cancelled: bool = False,
        retry_total: Optional[int] = None,
    ) -> str:
        total = len(results)
        success_count = sum(1 for row in results if bool(row.get("success")))
        retry_sum = retry_total
        if retry_sum is None:
            retry_sum = sum(max(0, int(row.get("retry_count", 0) or 0)) for row in results)
        success_rate = (success_count / total * 100.0) if total else 0.0
        columns = cls._batch_export_columns()
        lines = [
            f"# {title}",
            "",
            f"- 상태: {'취소됨' if cancelled else '완료'}",
            f"- 총 항목: {total}",
            f"- 성공: {success_count}",
            f"- 실패: {total - success_count}",
            f"- 성공률: {success_rate:.1f}%",
            f"- 총 재시도: {retry_sum}",
            "",
            "|" + "|".join(columns) + "|",
            "|" + "|".join("---" for _ in columns) + "|",
        ]
        for row in results:
            normalized = cls._batch_export_row(row)
            lines.append("|" + "|".join(cls._escape_markdown_cell(normalized.get(col, "")) for col in columns) + "|")
        return "\n".join(lines) + "\n"

    def _save_batch_results(
        self,
        results: List[Dict[str, Any]],
        fmt: str,
        *,
        cancelled: bool = False,
        title: str = "배치 테스트 결과",
        retry_total: Optional[int] = None,
    ):
        fmt = fmt.lower().strip()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if fmt == "csv":
            default_name = f"batch_results_{timestamp}.csv"
            file_filter = "CSV 파일 (*.csv)"
            content = self._batch_results_to_csv(results)
            suffix = ".csv"
        else:
            default_name = f"batch_results_{timestamp}.md"
            file_filter = "Markdown 파일 (*.md)"
            content = self._batch_results_to_markdown(
                results,
                title=title,
                cancelled=cancelled,
                retry_total=retry_total,
            )
            suffix = ".md"

        fname, _ = QFileDialog.getSaveFileName(self, "결과 저장", default_name, file_filter)
        if not fname:
            return
        if not fname.lower().endswith(suffix):
            fname += suffix
        try:
            with open(fname, "w", encoding="utf-8", newline="") as f:
                f.write(content)
            self._show_toast(f"결과 저장 완료: {fname}", "success", 4000)
        except Exception as e:
            self._show_toast(f"결과 저장 실패: {e}", "error")

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
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(["상태", "이름", "프레임", "창", "개수", "결과"])
        batch_hh = table.horizontalHeader()
        if batch_hh is not None:
            batch_hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            batch_hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            batch_hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            batch_hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
            batch_hh.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
            batch_hh.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)

        for r in results:
            row = table.rowCount()
            table.insertRow(row)
            success = bool(r.get("success"))
            status = QTableWidgetItem("✅" if success else "❌")
            status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, 0, status)
            table.setItem(row, 1, QTableWidgetItem(str(r.get("name", r.get("item_name", "-")))))
            table.setItem(row, 2, QTableWidgetItem(str(r.get("frame_path", ""))))
            table.setItem(row, 3, QTableWidgetItem(str(r.get("window_title", "") or r.get("window_url", "") or r.get("window_handle", ""))))
            table.setItem(row, 4, QTableWidgetItem(str(r.get("count", ""))))
            table.setItem(row, 5, QTableWidgetItem(str(r.get("msg", "Found" if success else "Not found"))))

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
        btn_csv = btn_box.addButton("CSV 저장", QDialogButtonBox.ButtonRole.ActionRole)
        btn_md = btn_box.addButton("Markdown 저장", QDialogButtonBox.ButtonRole.ActionRole)
        btn_csv.clicked.connect(lambda: self._save_batch_results(results, "csv", cancelled=cancelled, title=title, retry_total=retry_total))
        btn_md.clicked.connect(lambda: self._save_batch_results(results, "md", cancelled=cancelled, title=title, retry_total=retry_total))
        btn_box.rejected.connect(dialog.reject)
        layout.addWidget(btn_box)

        dialog.exec()
