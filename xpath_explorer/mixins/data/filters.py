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


class ExplorerDataFiltersMixin:
    def _refresh_filter_options_if_dirty(self, force: bool = False):
        """필터 옵션(카테고리/태그)을 필요할 때만 갱신."""
        if not (force or self._filter_options_dirty):
            return

        categories = sorted(self.config.get_categories())
        current_cat = self.combo_filter.currentData()
        if not isinstance(current_cat, str):
            current_cat = category_to_value(self.combo_filter.currentText() or "")
        self.combo_filter.blockSignals(True)
        self.combo_filter.clear()
        self.combo_filter.addItem("전체", "")
        for category in categories:
            self.combo_filter.addItem(category_to_label(category), category)
        if not current_cat:
            self.combo_filter.setCurrentIndex(0)
        else:
            category_index = self.combo_filter.findData(current_cat)
            if category_index >= 0:
                self.combo_filter.setCurrentIndex(category_index)
            else:
                self.combo_filter.setCurrentIndex(0)
        self.combo_filter.blockSignals(False)

        all_tags = set()
        for item in self.config.items:
            all_tags.update(item.tags)

        current_tag = self.combo_tag_filter.currentText() or "모든 태그"
        self.combo_tag_filter.blockSignals(True)
        self.combo_tag_filter.clear()
        self.combo_tag_filter.addItem("모든 태그")
        self.combo_tag_filter.addItems(sorted(all_tags))
        if current_tag == "모든 태그" or current_tag in all_tags:
            self.combo_tag_filter.setCurrentText(current_tag)
        else:
            self.combo_tag_filter.setCurrentIndex(0)
        self.combo_tag_filter.blockSignals(False)
        self._filter_tag = self.combo_tag_filter.currentText()

        self._filter_options_dirty = False

    def _item_matches_filters(self, item: XPathItem, target_cat: str) -> bool:
        normalized_category = category_to_value(target_cat or "")
        if normalized_category and item.category != normalized_category:
            return False

        if self._search_text:
            st = self._search_text.lower()
            if (
                st not in item.name.lower()
                and st not in item.description.lower()
                and st not in item.xpath.lower()
            ):
                return False

        if self._filter_favorites_only and not item.is_favorite:
            return False

        if self._filter_tag and self._filter_tag != "모든 태그":
            if self._filter_tag not in item.tags:
                return False

        return True

    def _collect_filtered_items(self, target_cat: str) -> List[XPathItem]:
        items_to_show = [item for item in self.config.items if self._item_matches_filters(item, target_cat)]
        items_to_show.sort(key=lambda x: x.sort_order)
        return items_to_show

    def _render_table_row(self, row: int, item: XPathItem):
        """Model/View 전환 이후 호환용 래퍼."""
        _ = row
        if self.table_model is not None:
            self.table_model.notify_item_changed(item.name)

    def _render_table_rows(self, items_to_show: List[XPathItem]):
        """Model/View 전환 이후 호환용 래퍼."""
        _ = items_to_show
        self._table_data_dirty = True

    def _update_table_summary(self, items_to_show: List[XPathItem]):
        verified_count = sum(1 for item in items_to_show if item.is_verified)
        self.lbl_summary.setText(f"총 {len(self.config.items)}개 (필터됨: {len(items_to_show)}개) | ✅ {verified_count}")
        if len(items_to_show) == 0 and len(self.config.items) > 0:
            self.lbl_summary.setText(f"검색 결과 없음 (전체: {len(self.config.items)}개)")
        elif len(self.config.items) == 0:
            self.lbl_summary.setText("항목이 없습니다. '+ 새 항목' 버튼을 클릭하여 추가하세요.")

    def _refresh_table(self, filter_cat=None, refresh_filters: bool = False):
        """테이블 갱신 - 모델/프록시 기반 필터 반영."""
        with perf_span("ui.refresh_table"):
            if self._table_data_dirty:
                self.table_model.set_items(self.config.items)
                self._table_data_dirty = False
            self._refresh_filter_options_if_dirty(force=refresh_filters)
            target_cat = category_to_value(filter_cat or "") if filter_cat is not None else ""
            if not target_cat:
                combo_data = self.combo_filter.currentData()
                if isinstance(combo_data, str):
                    target_cat = combo_data
                else:
                    target_cat = category_to_value(self.combo_filter.currentText() or "")
            self.table_proxy.set_category_filter(target_cat, "")
            self.table_proxy.set_tag_filter(self._filter_tag or "모든 태그", "모든 태그")
            self.table_proxy.set_favorites_only(self._filter_favorites_only)
            self.table_proxy.set_search_text(self._search_text)
            items_to_show = self._get_displayed_items()
            self._update_table_summary(items_to_show)
            return items_to_show

    def _on_search_text_changed(self, text):
        """[BUG-003] 검색어 변경 시 타이머 시작 (Debounce)"""
        self._search_text = text.strip()
        self._search_timer.start()
        # X 버튼 표시/숨김
        self.btn_clear_search.setVisible(bool(text.strip()))

    def _perform_search(self):
        """Debounce 후 실제 검색"""
        self._refresh_table()

    def _on_favorites_filter_changed(self, state):
        """즐겨찾기 필터 변경"""
        self._filter_favorites_only = (state == Qt.CheckState.Checked.value)
        self._refresh_table()

    def _on_tag_filter_changed(self, tag):
        """태그 필터 변경"""
        self._filter_tag = tag
        self._refresh_table()

    def _get_displayed_items(self) -> List[XPathItem]:
        items: List[XPathItem] = []
        rows = self.table_proxy.rowCount()
        for row in range(rows):
            item = self.table_proxy.get_item(row)
            if item:
                items.append(item)
        return items
