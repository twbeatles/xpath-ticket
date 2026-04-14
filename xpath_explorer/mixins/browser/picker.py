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


class ExplorerBrowserPickerMixin:
    def _start_picker(self):
        """요소 선택기 시작"""
        if not self.browser.is_alive():
            self._show_toast("브라우저를 먼저 실행해주세요.", "warning")
            return

        if self.picker_watcher and self.picker_watcher.isRunning():
            self._show_toast("요소 선택 모드가 이미 실행 중입니다.", "info")
            return

        watcher = PickerWatcher(self.browser)
        self.picker_watcher = watcher
        watcher.picked.connect(self._on_picked)
        watcher.cancelled.connect(self._on_pick_cancelled)
        
        self.browser.start_picker(overlay_mode=self.chk_overlay.isChecked())
        watcher.start()
        self._set_picker_action_enabled(True)

        self._show_toast(
            "요소 선택 모드 시작: 브라우저에서 요소에 마우스를 올린 뒤 '현재 요소 고정' 버튼을 누르세요. (ESC: 취소)",
            "info",
            6000,
        )

    def _force_lock_picker(self):
        """앱 버튼으로 현재 호버 요소를 강제 고정."""
        if not self.browser.is_alive():
            self._show_toast("브라우저가 연결되지 않았습니다.", "warning")
            return
        if not self.browser.is_picker_active():
            self._show_toast("먼저 '요소 선택 시작'을 실행하세요.", "warning")
            return
        if self.browser.lock_picker_current():
            self._show_toast("현재 요소를 고정했습니다. 브라우저에서 '이 요소 사용'을 눌러 캡처하세요.", "success")
        else:
            self._show_toast("고정할 요소를 찾지 못했습니다. 브라우저에서 대상 요소 위에 마우스를 올려주세요.", "warning")

    def _force_unlock_picker(self):
        """앱 버튼으로 현재 고정을 강제 해제."""
        if not self.browser.is_alive():
            self._show_toast("브라우저가 연결되지 않았습니다.", "warning")
            return
        if self.browser.unlock_picker_current():
            self._show_toast("요소 고정을 해제했습니다.", "info")
        else:
            self._show_toast("해제할 고정 요소가 없습니다.", "info")

    def _on_picked(self, result):
        """요소 선택 완료"""
        self._set_picker_action_enabled(False)
        if self.picker_watcher:
            self.picker_watcher.stop()
            self.picker_watcher.wait(WORKER_WAIT_TIMEOUT)
            self.picker_watcher = None
        
        if not result or not isinstance(result, dict):
            return

        xpath = result.get('xpath', '')
        css = result.get('css', '')
        tag = result.get('tag', '')
        text = result.get('text', '')
        frame = result.get('frame', 'main')
        window_handle = str(result.get('window_handle', '') or '')
        window_title = str(result.get('window_title', '') or '')
        window_url = str(result.get('window_url', '') or '')
        
        # 에디터 채우기
        self.input_xpath.setPlainText(xpath)
        self.input_css.setText(css)
        self.input_desc.setText(f"선택됨: {tag} ({text[:20]})")
        
        # 결과창 업데이트
        window_desc = window_title or window_handle or "-"
        self.txt_result.setPlainText(f"캡처 위치: {window_desc} / {frame}\n태그: {tag}\n텍스트: {text}")
        
        self._show_toast("요소 정보가 캡처되었습니다.", "success")
        
        # 이름 자동 제안
        if not self.input_name.text():
            suggested_name = f"ui_{tag}"
            if "login" in text.lower() or "login" in xpath.lower():
                suggested_name = "login_elem"
            self.input_name.setText(suggested_name)
            
        # 히스토리 추가
        self._add_to_history(xpath, css, tag, frame)

        item = self._get_current_item()
        if item is not None:
            item.found_window = window_handle or item.found_window
            item.found_window_title = window_title or item.found_window_title
            item.found_window_url = window_url or item.found_window_url
            item.found_frame = frame or item.found_frame

        if window_handle:
            self._set_window_combo_handle(window_handle, explicit=False)

    def _on_pick_cancelled(self):
        """요소 선택 취소"""
        self._set_picker_action_enabled(False)
        if self.picker_watcher:
            self.picker_watcher.stop()
            self.picker_watcher.wait(WORKER_WAIT_TIMEOUT)
            self.picker_watcher = None
        self._show_toast("요소 선택이 취소되었습니다.", "warning")
