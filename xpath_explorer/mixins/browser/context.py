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


class ExplorerBrowserContextMixin:
    def _set_picker_action_enabled(self, enabled: bool):
        """요소 선택기 고정/해제 버튼 활성 상태 동기화."""
        btn_lock = getattr(self, "btn_picker_lock", None)
        if btn_lock is not None:
            btn_lock.setEnabled(enabled)
        btn_unlock = getattr(self, "btn_picker_unlock", None)
        if btn_unlock is not None:
            btn_unlock.setEnabled(enabled)

    def _get_frame_combo_path(self) -> str:
        combo = self.__dict__.get("combo_frames")
        if combo is None:
            return "main"
        index = combo.currentIndex()
        if index < 0:
            return "main"
        data = combo.itemData(index)
        if isinstance(data, str) and data:
            return data
        return "main"

    def _get_window_combo_handle(self) -> str:
        combo = self.__dict__.get("combo_windows")
        if combo is None:
            return ""
        index = combo.currentIndex()
        if index < 0:
            return ""
        data = combo.itemData(index)
        if isinstance(data, str):
            return data
        return ""

    def _set_window_combo_handle(self, handle: Optional[str], explicit: Optional[bool] = None):
        combo = self.__dict__.get("combo_windows")
        if combo is None:
            if explicit is not None:
                self._window_selection_explicit = explicit
            return

        target = handle or ""
        index = combo.findData(target) if target else -1
        if index < 0 and combo.count() > 0:
            index = 0

        combo.blockSignals(True)
        try:
            if index >= 0:
                combo.setCurrentIndex(index)
        finally:
            combo.blockSignals(False)

        if explicit is not None:
            self._window_selection_explicit = explicit

    def _set_frame_combo_path(self, frame_path: Optional[str], explicit: Optional[bool] = None):
        combo = self.__dict__.get("combo_frames")
        if combo is None:
            if explicit is not None:
                self._frame_selection_explicit = explicit
            return

        target = frame_path or "main"
        index = combo.findData(target)
        if index < 0:
            target = "main"
            index = combo.findData(target)
        if index < 0 and combo.count() > 0:
            index = 0

        combo.blockSignals(True)
        try:
            if index >= 0:
                combo.setCurrentIndex(index)
        finally:
            combo.blockSignals(False)

        if explicit is not None:
            self._frame_selection_explicit = explicit

    def _get_current_item(self) -> Optional[XPathItem]:
        name_widget = self.__dict__.get("input_name")
        if name_widget is None or not hasattr(name_widget, "text"):
            return None
        name = str(name_widget.text() or "").strip()
        if not name:
            return None
        return self.config.get_item(name)

    def _resolve_active_window_context(self) -> Dict[str, str]:
        combo_handle = self._get_window_combo_handle()
        if getattr(self, "_window_selection_explicit", False):
            return {"handle": combo_handle or "", "title": "", "url": ""}

        item = self._get_current_item()
        if item is not None and (item.found_window or item.found_window_title or item.found_window_url):
            return {
                "handle": item.found_window or "",
                "title": item.found_window_title or "",
                "url": item.found_window_url or "",
            }

        return {"handle": combo_handle or "", "title": "", "url": ""}

    def _active_source_engine(self) -> str:
        return str(getattr(self, "_editing_source_engine", "") or "").strip().lower()

    def _active_validation_browser(self):
        from xpath_explorer.browser.engine_router import resolve_browser_for_item

        item = type("Item", (), {"source_engine": self._active_source_engine()})()
        browser, engine = resolve_browser_for_item(
            getattr(self, "browser", None),
            getattr(self, "pw_manager", None),
            item,
            fallback_selenium=False,
        )
        return browser, engine

    def _highlight_on_browser(self, browser, xpath: str, frame_path: Optional[str] = None) -> bool:
        if browser is None:
            return False
        if frame_path:
            switch = getattr(browser, "switch_to_frame_by_path", None) or getattr(browser, "switch_to_frame", None)
            if callable(switch):
                try:
                    switch(frame_path)
                except Exception:
                    pass
        highlight = getattr(browser, "highlight", None)
        if not callable(highlight):
            return False
        try:
            return bool(highlight(xpath, frame_path=frame_path))
        except TypeError:
            try:
                return bool(highlight(xpath, 2000))
            except TypeError:
                return bool(highlight(xpath))

    def _ensure_window_context_for_action(self) -> bool:
        context = self._resolve_active_window_context()
        handle = str(context.get("handle", "") or "")
        title = str(context.get("title", "") or "")
        url = str(context.get("url", "") or "")
        if not any((handle, title, url)):
            return True

        switch_context = getattr(self.browser, "switch_to_window_context", None)
        if callable(switch_context):
            ok = bool(switch_context(handle=handle, window_url=url, title=title))
        elif handle:
            ok = bool(self.browser.switch_window(handle))
        else:
            ok = True
        if not ok:
            return False

        get_current_window_metadata = getattr(self.browser, "get_current_window_metadata", None)
        if callable(get_current_window_metadata):
            try:
                current_window = get_current_window_metadata()
            except Exception:
                current_window = None
            if isinstance(current_window, dict):
                self._set_window_combo_handle(
                    str(current_window.get("handle", "") or ""),
                    explicit=getattr(self, "_window_selection_explicit", False),
                )
        return True

    def _resolve_active_frame_path(self) -> Optional[str]:
        combo_frame = self._get_frame_combo_path()
        if getattr(self, "_frame_selection_explicit", False):
            return combo_frame or "main"

        item = self._get_current_item()
        if item is not None and item.found_frame:
            return item.found_frame

        if combo_frame and combo_frame != "main":
            return combo_frame
        return None

    def _validate_xpath_for_ui(self, xpath: str, frame_path: Optional[str]) -> Dict[str, Any]:
        if frame_path is None:
            return cast(Dict[str, Any], self.browser.validate_xpath(xpath))

        try:
            try:
                info = self.browser.get_element_info(xpath, frame_path=frame_path, include_attributes=False)
            except TypeError:
                info = self.browser.get_element_info(xpath, frame_path=frame_path)
        except Exception as e:
            return {"found": False, "msg": str(e), "frame_path": frame_path}

        if not info or not info.get("found"):
            return {
                "found": False,
                "msg": str((info or {}).get("msg") or getattr(self.browser, "last_error", "") or "요소를 찾을 수 없습니다."),
                "frame_path": str((info or {}).get("frame_path", frame_path) or frame_path or ""),
                "window_handle": str((info or {}).get("window_handle", "") or ""),
                "window_title": str((info or {}).get("window_title", "") or ""),
                "window_url": str((info or {}).get("window_url", "") or ""),
            }

        return {
            "found": True,
            "count": int(info.get("count", 1) or 1),
            "tag": info.get("tag", ""),
            "text": info.get("text", ""),
            "frame_path": str(info.get("frame_path", frame_path) or frame_path or "main"),
            "window_handle": str(info.get("window_handle", "") or ""),
            "window_title": str(info.get("window_title", "") or ""),
            "window_url": str(info.get("window_url", "") or ""),
            "is_popup": bool(info.get("is_popup")),
            "msg": "",
        }

    def _set_live_preview_error(self, message: str):
        detail = (message or "").strip()
        if detail and len(detail) > 28:
            display = detail[:25] + "..."
        else:
            display = detail or "오류"
        self.lbl_live_preview.setText(f"⚠️ {display}")
        self.lbl_live_preview.setToolTip(detail)
        self.lbl_live_preview.setStyleSheet("color: #f38ba8; font-size: 11px;")
