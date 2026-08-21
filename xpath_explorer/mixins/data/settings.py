# -*- coding: utf-8 -*-
# pyright: reportAttributeAccessIssue=false, reportCallIssue=false, reportArgumentType=false
"""XPath Explorer mixin module (auto-split from legacy main file)."""

import csv
import json
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional

from xpath_explorer.qt_compat import (
    QAction,
    QApplication,
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHeaderView,
    QMenu,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    Qt,
    QVBoxLayout,
)

from xpath_explorer.core.constants import APP_TITLE, SITE_PRESETS, category_to_label, category_to_value
from xpath_explorer.core.config import XPathItem, SiteConfig
from xpath_explorer.core.perf import perf_span


class ExplorerDataSettingsMixin:
    def _on_preset_changed(self, preset_name):
        """프리셋 전환 시 편집 상태를 안전하게 초기화한다."""
        if preset_name == self.config.name:
            return

        if not self._confirm_discard_unsaved("프리셋 불러오기"):
            self.combo_preset.blockSignals(True)
            self.combo_preset.setCurrentText(self.config.name)
            self.combo_preset.blockSignals(False)
            return

        if len(self.config.items) > 0:
            reply = QMessageBox.question(
                self,
                '확인',
                f'"{preset_name}" 프리셋을 불러오시겠습니까?\n현재 작성 중인 목록은 초기화됩니다.',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                self.combo_preset.blockSignals(True)
                self.combo_preset.setCurrentText(self.config.name)
                self.combo_preset.blockSignals(False)
                return

        self.config = SiteConfig.from_preset(preset_name)
        self._editing_original_name = ''

        if self.config.login_url:
            self.input_url.setText(self.config.login_url)
        elif self.config.url:
            self.input_url.setText(self.config.url)

        self._table_data_dirty = True
        self._filter_options_dirty = True
        self._refresh_table(refresh_filters=True)
        self._reset_history_baseline()
        self._mark_config_clean()
        self._show_toast(f'{preset_name} 프리셋 로드 완료', 'success')

    def _increase_font(self):
        self._apply_font_size(self._font_size + 1)

    def _decrease_font(self):
        self._apply_font_size(self._font_size - 1)

    def _reset_font(self):
        self._apply_font_size(14)

    def _apply_font_size(self, size, notify: bool = True):
        self._font_size = max(8, min(size, 24))
        font = self.font()
        font.setPointSize(self._font_size)
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.setFont(font)
        if notify:
            self._show_toast(f"폰트 크기: {self._font_size}", "info", 1000)

    def _load_settings(self):
        """설정 로드"""
        geo = self.settings.value("geometry")
        if geo:
            self.restoreGeometry(geo)

        try:
            font_size = int(self.settings.value("ui/font_size", self._font_size))
        except (TypeError, ValueError):
            font_size = int(getattr(self, "_font_size", 14))
        self._apply_font_size(font_size, notify=False)

        preset_name = str(self.settings.value("ui/last_preset", "") or "").strip()
        if preset_name and preset_name in SITE_PRESETS:
            if hasattr(self, "combo_preset") and self.combo_preset is not None:
                self.combo_preset.blockSignals(True)
                self.combo_preset.setCurrentText(preset_name)
                self.combo_preset.blockSignals(False)
            if preset_name != self.config.name:
                self.config = SiteConfig.from_preset(preset_name)
                if self.config.login_url:
                    self.input_url.setText(self.config.login_url)
                elif self.config.url:
                    self.input_url.setText(self.config.url)
                self._table_data_dirty = True
                self._filter_options_dirty = True

        right_tab_raw = self.settings.value("ui/right_tab_index", 0)
        try:
            right_tab_index = int(right_tab_raw)
        except (TypeError, ValueError):
            right_tab_index = 0
        if hasattr(self, "right_tabs") and self.right_tabs is not None:
            if 0 <= right_tab_index < self.right_tabs.count():
                self.right_tabs.setCurrentIndex(right_tab_index)

        expanded_raw = self.settings.value("ui/url_panel_expanded", True)
        if isinstance(expanded_raw, str):
            expanded = expanded_raw.strip().lower() not in ("0", "false", "no", "off")
        else:
            expanded = bool(expanded_raw)
        if hasattr(self, "url_collapsible") and self.url_collapsible is not None:
            current_expanded = bool(getattr(self.url_collapsible, "_expanded", True))
            if current_expanded != expanded:
                self.url_collapsible.toggle_button.setChecked(expanded)
                self.url_collapsible.toggle(expanded)
