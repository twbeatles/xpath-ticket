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


class ExplorerBrowserExportMixin:
    def _screenshot_current_element(self):
        """현재 선택된 요소 스크린샷 저장"""
        xpath = self.input_xpath.toPlainText().strip()
        
        if not xpath:
            self._show_toast("XPath를 먼저 입력하세요.", "warning")
            return
        
        if not self.browser.is_alive():
            self._show_toast("브라우저를 먼저 연결하세요.", "warning")
            return
        if not self._ensure_window_context_for_action():
            last_error = getattr(self.browser, "last_error", "")
            self._show_toast(last_error or "대상 창을 찾을 수 없습니다.", "error")
            return
        
        # 저장 경로 선택
        fname, _ = QFileDialog.getSaveFileName(
            cast(QWidget, self), "스크린샷 저장", "element_screenshot.png", "PNG 파일 (*.png)"
        )
        
        if not fname:
            return
        
        # 스크린샷 저장
        frame_path = self._resolve_active_frame_path()
        success = self.browser.screenshot_element(xpath, fname, frame_path=frame_path)

        if success:
            self._show_toast(f"스크린샷 저장 완료: {fname}", "success")
            
            # 현재 항목에 스크린샷 경로 저장
            name = self.input_name.text().strip()
            item = self.config.get_item(name)
            if item:
                item.screenshot_path = fname
        else:
            last_error = getattr(self.browser, "last_error", "")
            self._show_toast(last_error or "스크린샷 저장 실패", "error")

    def _export_dom_selenium_htm(
        self,
        scope: Literal["all", "current"] = "all",
        include_frames: bool = True,
    ):
        """현재 Selenium 브라우저의 DOM을 단일 HTM으로 저장."""
        if not self.browser.is_alive():
            self._show_toast("브라우저를 먼저 연결하세요.", "warning")
            return

        default_name = f"selenium_dom_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.htm"
        fname, _ = QFileDialog.getSaveFileName(
            cast(QWidget, self),
            "DOM 저장",
            default_name,
            "HTM 파일 (*.htm *.html)",
        )
        if not fname:
            return

        if not fname.lower().endswith((".htm", ".html")):
            fname += ".htm"

        scope_label = "현재 창 + iframe" if scope == "current" and include_frames else ("현재 창" if scope == "current" else "전체")
        self._show_toast(f"DOM 추출 중... ({scope_label})", "info", 2000)
        try:
            snapshots = self.browser.collect_dom_snapshots(include_frames=include_frames, scope=scope)
            current_window = self.browser.get_current_window_metadata()
            report = render_dom_report_htm(
                snapshots,
                source_label="Selenium",
                scope=scope,
                selected_window_title=str(current_window.get("title", "") or ""),
                selected_window_url=str(current_window.get("url", "") or ""),
            )
            with open(fname, "w", encoding="utf-8") as f:
                f.write(report)

            fail_count = sum(1 for s in snapshots if s.error)
            self._show_toast(
                f"DOM 저장 완료: {fname} (문서 {len(snapshots)}개, 실패 {fail_count}개)",
                "success",
                5000,
            )
        except Exception as e:
            logger.error(f"Selenium DOM 저장 실패: {e}")
            self._show_toast(f"DOM 저장 실패: {e}", "error")
