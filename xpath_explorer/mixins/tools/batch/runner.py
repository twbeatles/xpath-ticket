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


class BatchRunnerMixin:
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
