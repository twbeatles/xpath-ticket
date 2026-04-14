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


class ExplorerBrowserValidationMixin:
    def _test_xpath(self):
        """XPath 단일 테스트"""
        xpath = self.input_xpath.toPlainText().strip()
        if not xpath: return
        
        if not self.browser.is_alive():
            self._show_toast("브라우저가 연결되지 않았습니다.", "error")
            return
            
        self._show_toast("XPath 검색 중...", "info")
        if not self._ensure_window_context_for_action():
            error_msg = str(getattr(self.browser, "last_error", "") or "대상 창을 찾을 수 없습니다.")
            self.txt_result.setPlainText(f"❌ 실패\n{error_msg}")
            self._show_toast(error_msg, "error")
            return
        
        original_frame = self.browser.current_frame_path

        target_frame = self._resolve_active_frame_path()

        try:
            result = self._validate_xpath_for_ui(xpath, target_frame)
            success = bool(result.get('found'))
            name = self.input_name.text().strip()
            self._record_validation_outcome(name, xpath, success, result)
            
            if success:
                msg = f"✅ 발견! (개수: {result.get('count', 1)})"
                detail = (
                    f"태그: {result.get('tag')}\n"
                    f"텍스트: {result.get('text')}\n"
                    f"창: {result.get('window_title') or result.get('window_handle') or '-'}\n"
                    f"프레임: {result.get('frame_path')}"
                )
                self.txt_result.setPlainText(msg + "\n" + detail)
                self._show_toast("요소를 찾았습니다!", "success")
                
                # 하이라이트
                if result.get('frame_path'):
                    self.browser.highlight(xpath, frame_path=result['frame_path'])
                else:
                    self.browser.highlight(xpath)
            else:
                error_msg = str(result.get('msg') or getattr(self.browser, "last_error", "") or "요소를 찾을 수 없습니다.")
                self.txt_result.setPlainText(f"❌ 실패\n{error_msg}")
                self._show_toast(error_msg, "error")
            self._refresh_table()
        finally:
            # 프레임 복구 (항상 원복)
            try:
                self.browser.switch_to_frame_by_path(original_frame if original_frame else "main")
            except Exception:
                pass

    def _highlight_xpath(self):
        """현재 XPath 하이라이트"""
        xpath = self.input_xpath.toPlainText().strip()
        if not xpath:
            return
        if not self.browser.is_alive():
            self._show_toast("브라우저가 연결되지 않았습니다.", "warning")
            return
        if not self._ensure_window_context_for_action():
            last_error = getattr(self.browser, "last_error", "")
            self._show_toast(last_error or "대상 창을 찾을 수 없습니다.", "error")
            return
        frame_path = self._resolve_active_frame_path()
        if not self.browser.highlight(xpath, frame_path=frame_path):
            last_error = getattr(self.browser, "last_error", "")
            self._show_toast(last_error or "하이라이트 실패", "error")

    def _validate_all(self):
        """전체 검증 시작"""
        if not self.config.items:
            self._show_toast("검증할 항목이 없습니다.", "warning")
            return
            
        if not self.browser.is_alive():
            self._show_toast("브라우저 연결 필요", "error")
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # 현재 열린 모든 윈도우 핸들 수집 (워커에 전달용)
        windows = [w['handle'] for w in self.browser.get_windows()]
        
        worker = ValidateWorker(self.browser, self.config.items, windows)
        self.validate_worker = worker
        worker.progress.connect(lambda v, m: (self.progress_bar.setValue(v), self.lbl_status.setText(m)))
        worker.validated.connect(self._on_validated)
        worker.finished.connect(self._on_validate_finished)
        worker.start()

    def _on_validated(self, name, result):
        """개별 검증 결과 처리"""
        item = self.config.get_item(name)
        if not item:
            return
        self._record_validation_outcome(name, item.xpath, bool(result.get('found')), result)

    def _record_validation_outcome(self, name: str, xpath: str, success: bool, result: Dict[str, Any]):
        """단일/전체/배치 검증 결과 공통 처리."""
        item = self.config.get_item(name)
        if not item:
            return

        item.is_verified = success
        item.record_test(success)

        frame_path = (result or {}).get('frame_path', '') or ''
        window_handle = str((result or {}).get('window_handle', '') or '')
        window_title = str((result or {}).get('window_title', '') or '')
        window_url = str((result or {}).get('window_url', '') or '')
        if success:
            item.element_tag = (result or {}).get('tag', '') or item.element_tag
            item.found_window = window_handle or item.found_window
            item.found_window_title = window_title or item.found_window_title
            item.found_window_url = window_url or item.found_window_url
            item.found_frame = frame_path or item.found_frame
            current_item = self._get_current_item()
            if (
                current_item is not None
                and current_item.name == item.name
                and not getattr(self, "_window_selection_explicit", False)
                and window_handle
            ):
                self._set_window_combo_handle(window_handle, explicit=False)
            if (
                current_item is not None
                and current_item.name == item.name
                and not getattr(self, "_frame_selection_explicit", False)
                and frame_path
            ):
                self._set_frame_combo_path(frame_path, explicit=False)

        if self.stats_manager:
            self.stats_manager.record_test(
                name,
                xpath,
                success,
                frame_path=frame_path,
                error_msg=(result or {}).get('msg', '') if not success else "",
            )

        if not success:
            if self.table_model is not None:
                self.table_model.notify_item_changed(name)
            return

        has_snapshot = False
        if self.diff_analyzer and hasattr(self.diff_analyzer, "has_snapshot"):
            has_snapshot = bool(self.diff_analyzer.has_snapshot(name))
        need_snapshot = (not has_snapshot) or not bool(item.element_attributes)

        try:
            info = self.browser.get_element_info(
                xpath,
                frame_path=frame_path,
                include_attributes=need_snapshot,
            )
        except TypeError:
            # 구 시그니처 호환
            info = self.browser.get_element_info(xpath, frame_path=frame_path)
        except Exception:
            info = None

        if not info or not info.get('found'):
            if self.table_model is not None:
                self.table_model.notify_item_changed(name)
            return

        item.element_tag = info.get('tag', item.element_tag) or item.element_tag
        item.found_window = str(info.get('window_handle', '') or item.found_window or '')
        item.found_window_title = str(info.get('window_title', '') or item.found_window_title or '')
        item.found_window_url = str(info.get('window_url', '') or item.found_window_url or '')
        item.found_frame = info.get('frame_path', frame_path or item.found_frame) or item.found_frame

        attrs = info.get('attributes', {})
        if need_snapshot and isinstance(attrs, dict):
            item.element_attributes = dict(attrs)
            snapshot_payload = {
                'xpath': xpath,
                'tag': info.get('tag', ''),
                'id': info.get('id', ''),
                'class': info.get('class', ''),
                'text': info.get('text', ''),
                'attributes': item.element_attributes,
            }
            if self.diff_analyzer and hasattr(self.diff_analyzer, "save_snapshot"):
                self.diff_analyzer.save_snapshot(name, snapshot_payload)

        if self.table_model is not None:
            self.table_model.notify_item_changed(name)

    def _on_validate_finished(self, found, total):
        """검증 완료"""
        self.progress_bar.setVisible(False)
        self._refresh_table()
        self._show_toast(f"검증 완료: {found}/{total} 성공", "success" if found==total else "warning")
        self.validate_worker = None
