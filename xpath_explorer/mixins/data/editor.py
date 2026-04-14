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


class ExplorerDataEditorMixin:
    def _on_table_clicked(self, index):
        """테이블 클릭 핸들러 (즐겨찾기 토글/삭제)."""
        if not index or not index.isValid():
            return

        item = self.table_proxy.get_item(index.row())
        if not item:
            return

        column = index.column()
        if column == 0:
            item.is_favorite = not item.is_favorite
            self.table_model.notify_item_changed(item.name)
            self.table_proxy.invalidateFilter()
            self._update_table_summary(self._get_displayed_items())
            status = "추가" if item.is_favorite else "해제"
            self._show_toast(f"'{item.name}' 즐겨찾기 {status}", "success", 1500)
        elif column == 6:
            self._delete_item(item.name)

    def _get_current_table_item(self) -> Optional[XPathItem]:
        """현재 선택된 목록 항목 반환."""
        selection_model = self.table.selectionModel()
        if selection_model is None:
            return None
        index = selection_model.currentIndex()
        if not index.isValid():
            return None
        return self.table_proxy.get_item(index.row())
        return None

    def _on_item_selected(self, *_args):
        """테이블 항목 선택 시 에디터로 로드"""
        item = self._get_current_table_item()
        if item:
            self._load_to_editor(item)

    def _load_to_editor(self, item: XPathItem):
        self._editing_original_name = item.name
        self.input_name.setText(item.name)
        category_index = self.input_category.findData(item.category)
        if category_index >= 0:
            self.input_category.setCurrentIndex(category_index)
        else:
            self.input_category.setCurrentText(category_to_label(item.category))
        self.input_desc.setText(item.description)
        self.input_xpath.setPlainText(item.xpath)
        self.input_css.setText(item.css_selector)
        self.input_tags.setText(', '.join(item.tags))

        meta = f"최근 검증: {'성공' if item.is_verified else '미검증'}\n"
        if item.element_tag:
            meta += f'태그: {item.element_tag}\n'
        if item.found_window_title:
            meta += f'창: {item.found_window_title}\n'
        elif item.found_window_url:
            meta += f'창 URL: {item.found_window_url}\n'
        elif item.found_window:
            meta += f'창 핸들: {item.found_window}\n'
        if item.found_frame:
            meta += f'프레임: {item.found_frame}\n'
        if item.test_count > 0:
            meta += f'테스트: {item.test_count}회 (성공률: {item.success_rate:.0f}%)\n'
        if item.last_tested:
            meta += f'최근 테스트: {item.last_tested[:10]}\n'

        self.txt_result.setPlainText(meta)

    def _add_new_item(self):
        """새 항목 추가 모드"""
        self._clear_editor()
        self.input_name.setFocus()
        self.table.clearSelection()

    def _clear_editor(self):
        self._editing_original_name = ''
        self.input_name.clear()
        self.input_desc.clear()
        self.input_xpath.clear()
        self.input_css.clear()
        self.txt_result.clear()
        self.input_tags.clear()
        default_category = self.input_category.findData('common')
        if default_category >= 0:
            self.input_category.setCurrentIndex(default_category)
        else:
            self.input_category.setCurrentText('공통')

    def _save_item(self):
        """항목 저장 - 이름 변경 충돌 방지 + 메타데이터 보존."""
        name = self.input_name.text().strip()
        xpath = self.input_xpath.toPlainText().strip()

        if not name or not xpath:
            self._show_toast('이름과 XPath는 필수입니다.', 'warning')
            return

        original_name = str(getattr(self, '_editing_original_name', '') or '').strip()
        original_item = self.config.get_item(original_name) if original_name else None
        existing = self.config.get_item(name)

        if original_name and original_name != name and existing is not None:
            self._show_toast(f"'{name}' 이름은 이미 사용 중입니다.", 'warning')
            return

        source_item = original_item if original_item is not None else existing
        action = 'add'
        action_desc = f'{name} 항목 추가'
        action_name = name
        if original_name and original_name != name and original_item is not None:
            action = 'rename'
            action_name = f'{original_name}->{name}'
            action_desc = f'{original_name} -> {name} 이름 변경'
        elif source_item is not None:
            action = 'update'
            action_desc = f'{name} 항목 수정'

        self.history_manager.push_state(self.config.items, action, action_name, action_desc)

        tags_text = self.input_tags.text().strip()
        tags = [t.strip() for t in tags_text.split(',') if t.strip()]

        category_value = self.input_category.currentData()
        if not isinstance(category_value, str) or not category_value:
            category_value = category_to_value(self.input_category.currentText().strip())

        item = XPathItem(
            name=name,
            xpath=xpath,
            category=category_value,
            description=self.input_desc.text(),
            css_selector=self.input_css.text().strip(),
            tags=tags,
        )

        if source_item:
            item.is_favorite = source_item.is_favorite
            item.test_count = source_item.test_count
            item.success_count = source_item.success_count
            item.last_tested = source_item.last_tested
            item.sort_order = source_item.sort_order
            item.is_verified = source_item.is_verified
            item.element_tag = source_item.element_tag
            item.element_text = source_item.element_text
            item.found_window = source_item.found_window
            item.found_window_title = source_item.found_window_title
            item.found_window_url = source_item.found_window_url
            item.found_frame = source_item.found_frame
            item.alternatives = list(source_item.alternatives or [])
            item.element_attributes = dict(source_item.element_attributes or {})
            item.screenshot_path = source_item.screenshot_path
            item.ai_generated = source_item.ai_generated

        current_window = None
        for browser_attr in ("browser", "pw_manager"):
            browser = getattr(self, browser_attr, None)
            if browser is not None and hasattr(browser, "get_current_window_metadata"):
                try:
                    current_window = browser.get_current_window_metadata()
                except Exception:
                    current_window = None
                if isinstance(current_window, dict) and any(
                    (
                        current_window.get("handle"),
                        current_window.get("title"),
                        current_window.get("url"),
                    )
                ):
                    break
        if isinstance(current_window, dict):
            item.found_window = str(current_window.get("handle", "") or item.found_window or "")
            item.found_window_title = str(current_window.get("title", "") or item.found_window_title or "")
            item.found_window_url = str(current_window.get("url", "") or item.found_window_url or "")

        if self.browser.current_frame_path:
            item.found_frame = self.browser.current_frame_path

        if original_name and original_name != name and original_item is not None:
            self.config.remove_item(original_name)

        self.config.add_or_update(item)
        self._table_data_dirty = True
        self._filter_options_dirty = True
        self._refresh_table(refresh_filters=True)
        self._update_undo_redo_actions()
        self.history_manager.sync_current_state(self.config.items)
        self._editing_original_name = name
        self._show_toast(f"'{name}' 저장 완료", 'success')

    def _delete_item(self, name):
        """항목 삭제 - v4.0: 히스토리 기록"""
        if QMessageBox.question(self, "삭제", f"'{name}' 항목을 삭제하시겠습니까?", 
                              QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            # v4.0: 삭제 전 히스토리 저장
            self.history_manager.push_state(
                self.config.items, "delete", name,
                f"{name} 항목 삭제"
            )
            self.config.remove_item(name)
            self._table_data_dirty = True
            self._filter_options_dirty = True
            self._refresh_table(refresh_filters=True)
            self._clear_editor()
            self._update_undo_redo_actions()  # v4.0
            # 히스토리 현재 상태 동기화 (변경 후)
            self.history_manager.sync_current_state(self.config.items)

    def _show_toast(self, message, toast_type="info", duration=3000):
        toast = getattr(self, "toast", None)
        if toast is None:
            return
        try:
            toast.show_toast(message, toast_type, duration)
        except RuntimeError:
            # QWidget teardown race: ignore toast update after destruction.
            return

    def _copy_xpath(self):
        xpath = self.input_xpath.toPlainText().strip()
        if xpath:
            clipboard = QApplication.clipboard()
            if clipboard is not None:
                clipboard.setText(xpath)
            self._show_toast("XPath 복사됨", "success", 1500)

    def _copy_css(self):
        css = self.input_css.text().strip()
        if css:
            clipboard = QApplication.clipboard()
            if clipboard is not None:
                clipboard.setText(css)
            self._show_toast("CSS 복사됨", "success", 1500)

    def _show_context_menu(self, pos):
        index = self.table.indexAt(pos)
        if index.isValid():
            self.table.selectRow(index.row())

        menu = QMenu(self)
        
        edit_action = QAction("✏️ 편집", self)
        edit_action.triggered.connect(self._on_item_selected)
        menu.addAction(edit_action)
        
        copy_action = QAction("📋 XPath 복사", self)
        copy_action.triggered.connect(lambda: self._copy_from_table_context(0))
        menu.addAction(copy_action)
        
        delete_action = QAction("🗑 삭제", self)
        delete_action.triggered.connect(self._delete_selected)
        menu.addAction(delete_action)
        
        viewport = self.table.viewport()
        if viewport is not None:
            menu.exec(viewport.mapToGlobal(pos))

    def _copy_from_table_context(self, type_idx):
        _ = type_idx
        item = self._get_current_table_item()
        if item:
            clipboard = QApplication.clipboard()
            if clipboard is not None:
                clipboard.setText(item.xpath)
            self._show_toast("복사되었습니다.", "success")

    def _delete_selected(self):
        item = self._get_current_table_item()
        if item:
            self._delete_item(item.name)

    def _show_shortcuts(self):
        shortcuts = [
            ("Ctrl+N", "새 설정"),
            ("Ctrl+O", "설정 열기"),
            ("Ctrl+S", "설정 저장"),
            ("Ctrl+T", "현재 XPath 테스트"),
            ("Ctrl+H", "XPath 히스토리"),
            ("F5", "전체 유효성 검사"),
            ("Ctrl++", "폰트 크게"),
            ("Ctrl+-", "폰트 작게")
        ]
        msg = "\n".join([f"{k}: {v}" for k, v in shortcuts])
        QMessageBox.information(self, "단축키 목록", msg)

    def _show_about(self):
        QMessageBox.about(self, "정보", f"{APP_TITLE}\n\n티켓 예매 사이트 자동화를 위한 XPath 도구입니다.")
