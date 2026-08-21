# pyright: reportAttributeAccessIssue=false, reportCallIssue=false, reportArgumentType=false, reportRedeclaration=false
# -*- coding: utf-8 -*-
"""XPath Explorer mixin module (auto-split from legacy main file)."""

import csv
import json
import os
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING, Tuple, cast, Literal

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
    APP_TITLE, APP_VERSION, SITE_PRESETS,
    BROWSER_CHECK_INTERVAL, SEARCH_DEBOUNCE_MS,
    LIVE_PREVIEW_DEBOUNCE_MS, WORKER_WAIT_TIMEOUT,
)
from xpath_explorer.ui.styles import STYLE
from xpath_explorer.core.config import XPathItem, SiteConfig
from xpath_explorer.ui.widgets import ToastWidget, NoWheelComboBox, AnimatedStatusIndicator, IconButton, CollapsibleBox
from xpath_explorer.browser.browser import BrowserManager
from xpath_explorer.workers.background import (
    PickerWatcher, ValidateWorker, LivePreviewWorker,
    AIGenerateWorker, DiffAnalyzeWorker, BatchTestWorker,
)
from xpath_explorer.core.perf import perf_span, log_perf_summary
from xpath_explorer.tools.codegen import CodeGenerator, CodeTemplate
from xpath_explorer.analysis.statistics import StatisticsManager
from xpath_explorer.tools.optimizer import XPathOptimizer, XPathAlternative
from xpath_explorer.state.history import HistoryManager
from xpath_explorer.tools.ai import XPathAIAssistant
from xpath_explorer.analysis.diff import XPathDiffAnalyzer
from xpath_explorer.ui.table_model import XPathItemTableModel
from xpath_explorer.ui.filter_proxy import XPathFilterProxyModel
from xpath_explorer.browser.dom_export import render_dom_report_htm

from xpath_explorer.runtime import logger


class ExplorerBrowserPreviewMixin:
    def _on_xpath_text_changed(self):
        """XPath 입력 변경 시 실시간 미리보기 타이머 시작"""
        self._live_preview_timer.start()

    def _update_live_preview(self):
        """실시간 매칭 요소 수 업데이트 (비동기)"""
        with perf_span("ui.update_live_preview"):
            xpath = self.input_xpath.toPlainText().strip()
        
            if not xpath:
                self.lbl_live_preview.setText("🔍 매칭: -")
                self.lbl_live_preview.setStyleSheet("color: #6c7086; font-size: 11px;")
                return
            
            from xpath_explorer.workers.driver_guard import exclusive_driver_worker_running

            engine_browser, engine_name = self._active_validation_browser()
            if engine_browser is None or not getattr(engine_browser, "is_alive", lambda: False)():
                label = "Playwright 없음" if engine_name == "playwright" else "브라우저 없음"
                self.lbl_live_preview.setText(f"🔍 매칭: ({label})")
                self.lbl_live_preview.setStyleSheet("color: #6c7086; font-size: 11px;")
                return
            busy, _name = exclusive_driver_worker_running(self)
            if busy:
                return

            self._live_preview_request_id += 1
            request_id = self._live_preview_request_id

            if self.live_preview_worker and self.live_preview_worker.isRunning():
                self.live_preview_worker.cancel()
                self.live_preview_worker.wait(WORKER_WAIT_TIMEOUT)

            self.lbl_live_preview.setText("🔍 매칭: 계산 중...")
            self.lbl_live_preview.setStyleSheet("color: #89b4fa; font-size: 11px;")

            from xpath_explorer.mixins import browser_mixin as browser_mixin_module

            window_context: Dict[str, str] = {}
            source_engine = str(getattr(self, "_editing_source_engine", "") or "")
            if source_engine == "playwright":
                window_context = {
                    "handle": "",
                    "title": str(getattr(self, "_editing_source_window_title", "") or ""),
                    "url": str(getattr(self, "_editing_source_window_url", "") or ""),
                }
            else:
                item = None
                original_name = str(getattr(self, "_editing_original_name", "") or "")
                if original_name:
                    item = self.config.get_item(original_name)
                if item is None:
                    try:
                        item = self._get_current_table_item()
                    except Exception:
                        item = None
                if item is not None:
                    window_context = {
                        "handle": str(getattr(item, "found_window", "") or ""),
                        "title": str(getattr(item, "found_window_title", "") or ""),
                        "url": str(getattr(item, "found_window_url", "") or ""),
                    }
                    if str(getattr(item, "source_engine", "") or "").lower() == "playwright":
                        window_context["handle"] = ""

            frame_path = self._resolve_active_frame_path()
            try:
                worker = browser_mixin_module.LivePreviewWorker(
                    engine_browser,
                    xpath,
                    request_id,
                    frame_path=frame_path,
                    window_context=window_context,
                )
            except TypeError:
                worker = browser_mixin_module.LivePreviewWorker(
                    engine_browser,
                    xpath,
                    request_id,
                    frame_path=frame_path,
                )
            worker.counted.connect(self._on_live_preview_counted)
            worker.failed.connect(self._on_live_preview_failed)
            worker.finished.connect(lambda w=worker: self._on_live_preview_worker_finished(w))
            self.live_preview_worker = worker
            worker.start()

    def _on_live_preview_counted(self, request_id: int, count: int):
        if request_id != self._live_preview_request_id:
            return

        if count < 0:
            self._set_live_preview_error(getattr(self.browser, "last_error", ""))
        elif count == 0:
            self.lbl_live_preview.setText("❌ 매칭: 0개")
            self.lbl_live_preview.setToolTip("")
            self.lbl_live_preview.setStyleSheet("color: #f38ba8; font-size: 11px;")
        elif count == 1:
            self.lbl_live_preview.setText("✅ 매칭: 1개")
            self.lbl_live_preview.setToolTip("")
            self.lbl_live_preview.setStyleSheet("color: #a6e3a1; font-size: 11px;")
        else:
            self.lbl_live_preview.setText(f"🔍 매칭: {count}개")
            self.lbl_live_preview.setToolTip("")
            self.lbl_live_preview.setStyleSheet("color: #fab387; font-size: 11px;")

    def _on_live_preview_failed(self, request_id: int, _error: str):
        if request_id != self._live_preview_request_id:
            return
        last_error = getattr(self.browser, "last_error", "") or _error
        self._set_live_preview_error(last_error)

    def _on_live_preview_worker_finished(self, worker):
        if self.live_preview_worker is worker:
            self.live_preview_worker = None
