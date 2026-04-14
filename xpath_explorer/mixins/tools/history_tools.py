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


class ExplorerHistoryToolsMixin:
    def _reset_history_baseline(self):
        """현재 항목 목록을 Undo/Redo 기준 상태로 재설정."""
        self.history_manager.initialize(self.config.items)
        self._update_undo_redo_actions()

    def _update_undo_redo_actions(self):
        """Undo/Redo 액션 상태 업데이트"""
        if self.undo_action is None or self.redo_action is None:
            return
        self.undo_action.setEnabled(self.history_manager.can_undo())
        self.redo_action.setEnabled(self.history_manager.can_redo())
        
        if self.history_manager.can_undo():
            self.undo_action.setText(f"↩️ 실행 취소 ({self.history_manager.get_undo_description()})")
        else:
            self.undo_action.setText("↩️ 실행 취소")

    def _undo(self):
        """실행 취소"""
        restored = self.history_manager.undo()
        if restored is not None:
            self._restore_items_from_dicts(restored)
            self._filter_options_dirty = True
            self._refresh_table(refresh_filters=True)
            self._update_undo_redo_actions()
            self._show_toast("실행 취소됨", "info")

    def _redo(self):
        """다시 실행"""
        restored = self.history_manager.redo()
        if restored is not None:
            self._restore_items_from_dicts(restored)
            self._filter_options_dirty = True
            self._refresh_table(refresh_filters=True)
            self._update_undo_redo_actions()
            self._show_toast("다시 실행됨", "info")

    def _restore_items_from_dicts(self, item_dicts: list):
        """딕셔너리 리스트에서 XPathItem 복원"""
        restored_items = []
        for d in item_dicts:
            item = XPathItem(
                name=d.get('name', ''),
                xpath=d.get('xpath', ''),
                category=d.get('category', 'common'),
                description=d.get('description', ''),
                css_selector=d.get('css_selector', ''),
                is_verified=d.get('is_verified', False),
                element_tag=d.get('element_tag', ''),
                element_text=d.get('element_text', ''),
                found_window=d.get('found_window', ''),
                found_window_title=d.get('found_window_title', ''),
                found_window_url=d.get('found_window_url', ''),
                found_frame=d.get('found_frame', ''),
                is_favorite=d.get('is_favorite', False),
                tags=d.get('tags', []),
                test_count=d.get('test_count', 0),
                success_count=d.get('success_count', 0),
                last_tested=d.get('last_tested', ''),
                sort_order=d.get('sort_order', 0),
                alternatives=d.get('alternatives', []),
                element_attributes=d.get('element_attributes', {}),
                screenshot_path=d.get('screenshot_path', ''),
                ai_generated=d.get('ai_generated', False)
            )
            restored_items.append(item)
        self.config.replace_items(restored_items)
        self._table_data_dirty = True

    def _save_item_with_history(self):
        """항목 저장 (히스토리 기록 포함)"""
        name = self.input_name.text().strip()
        existing = self.config.get_item(name)
        action = "update" if existing else "add"
        
        # 변경 전 상태 저장
        self.history_manager.push_state(
            self.config.items, action, name,
            f"{name} 항목 {'수정' if existing else '추가'}"
        )
        
        # 원래 저장 로직은 _save_item()에서 처리
        self._update_undo_redo_actions()

    def _save_settings(self):
        """UI 설정 저장."""
        if not hasattr(self, "settings") or self.settings is None:
            return

        self.settings.setValue("ui/font_size", int(getattr(self, "_font_size", 14)))

        right_tab_index = 0
        right_tabs = getattr(self, "right_tabs", None)
        if right_tabs is not None and hasattr(right_tabs, "currentIndex"):
            try:
                right_tab_index = int(right_tabs.currentIndex())
            except Exception:
                right_tab_index = 0
        self.settings.setValue("ui/right_tab_index", right_tab_index)

        url_panel_expanded = True
        url_collapsible = getattr(self, "url_collapsible", None)
        if url_collapsible is not None:
            url_panel_expanded = bool(getattr(url_collapsible, "_expanded", True))
        self.settings.setValue("ui/url_panel_expanded", url_panel_expanded)

        preset_name = ""
        combo_preset = getattr(self, "combo_preset", None)
        if combo_preset is not None and hasattr(combo_preset, "currentText"):
            try:
                preset_name = str(combo_preset.currentText() or "").strip()
            except Exception:
                preset_name = ""
        if not preset_name and hasattr(self, "config") and getattr(self, "config", None) is not None:
            preset_name = str(getattr(self.config, "name", "") or "").strip()
        if preset_name:
            self.settings.setValue("ui/last_preset", preset_name)
