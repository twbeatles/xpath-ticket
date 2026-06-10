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


class FeatureDiagnosticsMixin:
    @staticmethod
    def _md_value(value: Any) -> str:
        text = str(value if value is not None else "")
        return text.replace("|", "\\|").replace("\r\n", "<br>").replace("\n", "<br>")

    def _render_feature_diagnostics_markdown(self) -> str:
        """현재 기능/문맥 상태를 Markdown 리포트로 렌더링."""
        lines = [
            "# XPath Explorer 기능 진단 리포트",
            "",
            f"- 생성 시각: {datetime.now().isoformat(timespec='seconds')}",
            f"- 설정 이름: {self._md_value(getattr(getattr(self, 'config', None), 'name', ''))}",
            f"- 저장 항목 수: {len(getattr(getattr(self, 'config', None), 'items', []) or [])}",
            "",
            "## Selenium 상태",
        ]

        browser = getattr(self, "browser", None)
        selenium_alive = False
        if browser is not None:
            try:
                selenium_alive = bool(browser.is_alive())
            except Exception:
                selenium_alive = False
        lines.append(f"- 연결: {'예' if selenium_alive else '아니오'}")
        if browser is not None:
            try:
                meta = browser.get_current_window_metadata()
            except Exception:
                meta = {}
            if isinstance(meta, dict):
                lines.extend([
                    f"- 현재 창 핸들: {self._md_value(meta.get('handle', ''))}",
                    f"- 현재 창 제목: {self._md_value(meta.get('title', ''))}",
                    f"- 현재 URL: {self._md_value(meta.get('url', ''))}",
                ])
            lines.append(f"- 현재 프레임: {self._md_value(getattr(browser, 'current_frame_path', '') or 'main')}")

        combo_windows = getattr(self, "combo_windows", None)
        combo_frames = getattr(self, "combo_frames", None)
        if combo_windows is not None:
            lines.append(f"- UI 선택 창: {self._md_value(combo_windows.currentText())}")
        if combo_frames is not None:
            lines.append(f"- UI 선택 프레임: {self._md_value(combo_frames.currentText())}")

        lines.extend(["", "## Playwright 상태"])
        pw_manager = getattr(self, "pw_manager", None)
        pw_alive = False
        if pw_manager is not None:
            try:
                pw_alive = bool(pw_manager.is_alive())
            except Exception:
                pw_alive = False
        lines.append(f"- 연결: {'예' if pw_alive else '아니오'}")
        if pw_manager is not None:
            try:
                meta = pw_manager.get_current_window_metadata()
            except Exception:
                meta = {}
            if isinstance(meta, dict):
                lines.extend([
                    f"- 현재 창 핸들: {self._md_value(meta.get('handle', ''))}",
                    f"- 현재 창 제목: {self._md_value(meta.get('title', ''))}",
                    f"- 현재 URL: {self._md_value(meta.get('url', ''))}",
                ])
            current_frame = getattr(pw_manager, "_current_frame", None)
            frame_label = ""
            if current_frame is not None:
                frame_label = str(getattr(current_frame, "name", "") or getattr(current_frame, "url", "") or "")
            lines.append(f"- 현재 프레임: {self._md_value(frame_label or 'main')}")

        lines.extend(["", "## 저장 항목 문맥", "|이름|창|URL|프레임|검증|", "|---|---|---|---|---|"])
        items = list(getattr(getattr(self, "config", None), "items", []) or [])
        if items:
            for item in items[:100]:
                lines.append(
                    "|"
                    + "|".join(
                        [
                            self._md_value(getattr(item, "name", "")),
                            self._md_value(getattr(item, "found_window_title", "") or getattr(item, "found_window", "")),
                            self._md_value(getattr(item, "found_window_url", "")),
                            self._md_value(getattr(item, "found_frame", "")),
                            "성공" if bool(getattr(item, "is_verified", False)) else "미검증/실패",
                        ]
                    )
                    + "|"
                )
        else:
            lines.append("|-|-|-|-|-|")

        lines.extend(["", "## 최근 검증 실패", "|시각|항목|프레임|오류|", "|---|---|---|---|"])
        recent_failures: List[Any] = []
        stats_manager = getattr(self, "stats_manager", None)
        if stats_manager is not None and hasattr(stats_manager, "get_recent_history"):
            try:
                recent_failures = [row for row in stats_manager.get_recent_history(50) if not bool(getattr(row, "success", False))][:20]
            except Exception:
                recent_failures = []
        if recent_failures:
            for row in recent_failures:
                lines.append(
                    "|"
                    + "|".join(
                        [
                            self._md_value(getattr(row, "timestamp", "")),
                            self._md_value(getattr(row, "item_name", "")),
                            self._md_value(getattr(row, "frame_path", "")),
                            self._md_value(getattr(row, "error_msg", "")),
                        ]
                    )
                    + "|"
                )
        else:
            lines.append("|-|-|-|-|")

        lines.extend(["", "## Telemetry 요약"])
        try:
            telemetry = error_telemetry.get_summary(top_n=10)
        except Exception:
            telemetry = {}
        lines.extend([
            f"- 총 에러: {telemetry.get('total_errors', 0)}",
            f"- 치명적 에러: {telemetry.get('critical_count', 0)}",
            f"- 최근 버퍼 이벤트: {telemetry.get('buffered_events', 0)}",
        ])
        top_errors = telemetry.get("top_errors", [])
        if top_errors:
            lines.extend(["", "|모듈|함수|메시지|횟수|", "|---|---|---|---|"])
            for row in top_errors:
                lines.append(
                    "|"
                    + "|".join(
                        [
                            self._md_value(row.get("module", "")),
                            self._md_value(row.get("function", "")),
                            self._md_value(row.get("message", "")),
                            self._md_value(row.get("count", 0)),
                        ]
                    )
                    + "|"
                )
        return "\n".join(lines) + "\n"

    def _save_feature_diagnostics_report(self):
        default_name = f"feature_diagnostics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        fname, _ = QFileDialog.getSaveFileName(
            self,
            "기능 진단 리포트 저장",
            default_name,
            "Markdown 파일 (*.md)",
        )
        if not fname:
            return
        if not fname.lower().endswith(".md"):
            fname += ".md"
        try:
            with open(fname, "w", encoding="utf-8") as f:
                f.write(self._render_feature_diagnostics_markdown())
            self._show_toast(f"진단 리포트 저장 완료: {fname}", "success", 4000)
        except Exception as e:
            self._show_toast(f"진단 리포트 저장 실패: {e}", "error")
