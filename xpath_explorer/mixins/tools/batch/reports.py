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


class BatchReportMixin:
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
