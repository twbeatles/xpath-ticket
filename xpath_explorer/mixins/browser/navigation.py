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


class ExplorerBrowserNavigationMixin:
    def _check_browser(self):
        """브라우저 연결 상태 주기적 확인 (popup/window 변화 포함)."""
        is_alive = self.browser.is_alive()
        current_state = getattr(self, '_last_browser_state', None)

        window_count = 0
        if is_alive and self.browser.driver is not None:
            try:
                window_count = len(self.browser.driver.window_handles)
            except Exception:
                window_count = 0

        # 상태는 같아도 popup/window 수 변화가 있으면 목록을 갱신한다.
        if current_state == is_alive:
            last_window_count = getattr(self, "_last_window_count", 0)
            if is_alive and window_count != last_window_count:
                self._last_window_count = window_count
                popup_opened = window_count > last_window_count
                self._refresh_windows(prefer_popup=popup_opened)
                if popup_opened and window_count > 1:
                    self._show_toast("새 팝업 창을 감지했습니다.", "info", 1800)
            return

        self._last_browser_state = is_alive
        self._last_window_count = window_count

        # AnimatedStatusIndicator 업데이트
        self.status_indicator.set_connected(is_alive)

        if is_alive:
            self.lbl_status.setText(f"{self.config.name}")
            self.lbl_status.setObjectName("status_connected")
            self.btn_open.setText("🔴 브라우저 닫기")
            self.btn_open.setObjectName("danger")
            self._refresh_windows(prefer_popup=True)
        else:
            self.lbl_status.setText("연결 안됨")
            self.lbl_status.setObjectName("status_disconnected")
            self.btn_open.setText("🌐 브라우저 열기")
            self.btn_open.setObjectName("primary")
            self.combo_windows.clear()
            self.combo_frames.clear()
            self._frame_selection_explicit = False
            self._window_selection_explicit = False
            self._last_window_count = 0
            self._set_picker_action_enabled(False)

        # 스타일 리로드 (색상 변경 적용)
        status_style = self.lbl_status.style()
        if status_style is not None:
            status_style.unpolish(self.lbl_status)
            status_style.polish(self.lbl_status)
        button_style = self.btn_open.style()
        if button_style is not None:
            button_style.unpolish(self.btn_open)
            button_style.polish(self.btn_open)

    def _toggle_browser(self):
        """브라우저 열기/닫기"""
        if self.browser.is_alive():
            if self.picker_watcher:
                self.picker_watcher.stop()
                self.picker_watcher.wait(WORKER_WAIT_TIMEOUT)
                self.picker_watcher = None
            self.browser.close()
            self._set_picker_action_enabled(False)
            self._show_toast("브라우저가 종료되었습니다.", "info")
        else:
            # 설정의 URL 사용
            start_url = self.config.login_url or self.config.url
            if not start_url:
                start_url = "about:blank"
                
            self._show_toast("브라우저를 시작합니다...", "info", 5000)
            
            if self.browser.create_driver():
                self.browser.navigate(start_url)
                self.input_url.setText(start_url)
                self._refresh_windows()
                self._show_toast("브라우저가 실행되었습니다.", "success")
            else:
                last_error = getattr(self.browser, "last_error", "")
                self._show_toast(last_error or "브라우저 실행 실패. 드라이버를 확인하세요.", "error")

    def _navigate(self):
        """URL 이동"""
        url = self.input_url.text().strip()
        if not url: return
        
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            self.input_url.setText(url)  # 정규화된 URL로 입력창 업데이트
            
        if self.browser.is_alive():
            self.browser.navigate(url)
            self._show_toast(f"이동 중: {url}", "info")
        else:
            self._show_toast("브라우저가 실행되지 않았습니다.", "warning")

    def _browser_back(self):
        if not self.browser.is_alive():
            return
        driver = self.browser.driver
        if driver is not None:
            driver.back()

    def _browser_forward(self):
        if not self.browser.is_alive():
            return
        driver = self.browser.driver
        if driver is not None:
            driver.forward()

    def _browser_refresh(self):
        if not self.browser.is_alive():
            return
        driver = self.browser.driver
        if driver is not None:
            driver.refresh()

    def _refresh_windows(self, prefer_popup: bool = False):
        """윈도우 목록 갱신 (팝업 우선 정렬 + 선택 유지)."""
        selected_handle = self._get_window_combo_handle()

        self.combo_windows.blockSignals(True)
        self.combo_windows.clear()

        windows = self.browser.get_windows()
        handles: List[str] = []
        popup_handle = None
        current_handle = None

        for i, win in enumerate(windows):
            title = win['title'] if win['title'] else f"창 {i+1}"
            if len(title) > 30:
                title = title[:27] + "..."

            is_popup = bool(win.get("is_popup"))
            label_prefix = "[팝업] " if is_popup else ""
            self.combo_windows.addItem(f"{label_prefix}{title}", win['handle'])
            handles.append(win['handle'])

            if is_popup and popup_handle is None:
                popup_handle = win['handle']
            if win.get('current'):
                current_handle = win['handle']

        target_handle = None
        if selected_handle in handles:
            target_handle = selected_handle
        elif prefer_popup and popup_handle:
            target_handle = popup_handle
        elif current_handle in handles:
            target_handle = current_handle
        elif popup_handle:
            target_handle = popup_handle
        elif handles:
            target_handle = handles[0]

        if target_handle in handles:
            self._set_window_combo_handle(
                target_handle,
                explicit=getattr(self, "_window_selection_explicit", False),
            )

        self.combo_windows.blockSignals(False)

        if target_handle:
            try:
                driver = self.browser.driver
                current_driver_handle = driver.current_window_handle if driver is not None else None
            except Exception:
                current_driver_handle = None

            if target_handle != current_driver_handle:
                self.browser.switch_window(target_handle)

        self._scan_frames()

    def _on_window_changed(self, index):
        """윈도우 전환"""
        if index < 0:
            self._window_selection_explicit = False
            return

        handle = self.combo_windows.itemData(index)
        self._window_selection_explicit = True
        if self.browser.switch_window(handle):
            self._scan_frames()
            self._show_toast("윈도우가 전환되었습니다.", "success")
        else:
            self._show_toast("윈도우 전환 실패", "error")
            self._refresh_windows()

    def _on_frame_changed(self, index):
        """프레임 전환"""
        if index < 0:
            self._frame_selection_explicit = False
            return

        target_frame = self._get_frame_combo_path()
        self._frame_selection_explicit = True

        if not self.browser.is_alive():
            return

        if self.browser.switch_to_frame_by_path(target_frame):
            self._show_toast("프레임이 전환되었습니다.", "success")
        else:
            last_error = getattr(self.browser, "last_error", "")
            self._show_toast(last_error or "프레임 전환 실패", "error")

    def _scan_frames(self):
        """iframe 목록 스캔"""
        with perf_span("ui.scan_frames"):
            manual_target = self._get_frame_combo_path() if getattr(self, "_frame_selection_explicit", False) else None
            self.combo_frames.blockSignals(True)
            try:
                self.combo_frames.clear()
                self.combo_frames.addItem("메인 문서", "main")
                
                if not self.browser.is_alive():
                    return
                    
                try:
                    frames = self.browser.get_all_frames(force_refresh=True)
                except TypeError:
                    frames = self.browser.get_all_frames()
                for path, identifier in frames:
                    indent = "  " * path.count('/')
                    self.combo_frames.addItem(f"{indent}📄 {identifier}", path)
                if manual_target and self.combo_frames.findData(manual_target) < 0:
                    manual_target = None
                    self._frame_selection_explicit = False
                target_frame = manual_target
                if not target_frame:
                    item = self._get_current_item()
                    item_frame = item.found_frame if item is not None else ""
                    if item_frame and self.combo_frames.findData(item_frame) >= 0:
                        target_frame = item_frame
                    elif self.browser.current_frame_path and self.combo_frames.findData(self.browser.current_frame_path) >= 0:
                        target_frame = self.browser.current_frame_path
                    else:
                        target_frame = "main"
                self._set_frame_combo_path(target_frame, explicit=getattr(self, "_frame_selection_explicit", False))
                self._show_toast(f"{len(frames)}개의 프레임을 찾았습니다.", "info")
            finally:
                self.combo_frames.blockSignals(False)
