# -*- coding: utf-8 -*-
"""XPath Explorer mixin module (auto-split from legacy main file)."""

import csv
import json
import os
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast

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
    category_to_label, category_to_value,
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

from xpath_explorer.runtime import logger


class ExplorerDataMixin:
    def _on_preset_changed(self, preset_name):
        """
        [BUG-004] 프리셋 변경 시 확인 로직 개선
        기존: 같은 프리셋을 다시 선택해도 변경 확인창 뜸
        수정: 현재 config.name과 다를 때만 확인
        """
        if preset_name == self.config.name:
            return

        if len(self.config.items) > 0:
            reply = QMessageBox.question(
                self, '확인',
                f'"{preset_name}" 프리셋을 불러오시겠습니까?\n현재 작성 중인 목록은 초기화됩니다.',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                # 콤보박스를 이전 값으로 되돌려야 함 (구현 복잡성으로 인해 여기선 생략하고, 그냥 로드 취소)
                self.combo_preset.blockSignals(True)
                self.combo_preset.setCurrentText(self.config.name)
                self.combo_preset.blockSignals(False)
                return

        self.config = SiteConfig.from_preset(preset_name)
        
        # URL 입력창 업데이트
        if self.config.login_url:
            self.input_url.setText(self.config.login_url)
        elif self.config.url:
            self.input_url.setText(self.config.url)

        self._table_data_dirty = True
        self._filter_options_dirty = True
        self._refresh_table(refresh_filters=True)
        self._reset_history_baseline()
        self._show_toast(f"{preset_name} 프리셋 로드 완료", "success")

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
        self.input_name.setText(item.name)
        category_index = self.input_category.findData(item.category)
        if category_index >= 0:
            self.input_category.setCurrentIndex(category_index)
        else:
            self.input_category.setCurrentText(category_to_label(item.category))
        self.input_desc.setText(item.description)
        self.input_xpath.setPlainText(item.xpath)
        self.input_css.setText(item.css_selector)
        # v3.3: 태그 로드
        self.input_tags.setText(", ".join(item.tags))
        
        # 결과창에 메타데이터 표시
        meta = f"최근 검증: {'성공' if item.is_verified else '미검증'}\n"
        if item.element_tag: meta += f"태그: {item.element_tag}\n"
        if item.found_frame: meta += f"프레임: {item.found_frame}\n"
        # v3.3: 통계 표시
        if item.test_count > 0:
            meta += f"테스트: {item.test_count}회 (성공률: {item.success_rate:.0f}%)\n"
        if item.last_tested:
            meta += f"최근 테스트: {item.last_tested[:10]}\n"
        
        self.txt_result.setPlainText(meta)

    def _add_new_item(self):
        """새 항목 추가 모드"""
        self._clear_editor()
        self.input_name.setFocus()
        self.table.clearSelection()

    def _clear_editor(self):
        self.input_name.clear()
        self.input_desc.clear()
        self.input_xpath.clear()
        self.input_css.clear()
        self.txt_result.clear()
        self.input_tags.clear()  # v3.3
        default_category = self.input_category.findData("common")
        if default_category >= 0:
            self.input_category.setCurrentIndex(default_category)
        else:
            self.input_category.setCurrentText("공통")

    def _save_item(self):
        """항목 저장 - v3.3: 태그 및 통계 보존, v4.0: 히스토리 기록"""
        name = self.input_name.text().strip()
        xpath = self.input_xpath.toPlainText().strip()
        
        if not name or not xpath:
            self._show_toast("이름과 XPath는 필수입니다.", "warning")
            return
        
        # 기존 항목이 있는지 확인 (통계 보존용)
        existing = self.config.get_item(name)
        
        # v4.0: 변경 전 상태 히스토리에 저장
        action = "update" if existing else "add"
        self.history_manager.push_state(
            self.config.items, action, name,
            f"{name} 항목 {'수정' if existing else '추가'}"
        )
        
        # v3.3: 태그 파싱
        tags_text = self.input_tags.text().strip()
        tags = [t.strip() for t in tags_text.split(",") if t.strip()]
            
        category_value = self.input_category.currentData()
        if not isinstance(category_value, str) or not category_value:
            category_value = category_to_value(self.input_category.currentText().strip())

        item = XPathItem(
            name=name,
            xpath=xpath,
            category=category_value,
            description=self.input_desc.text(),
            css_selector=self.input_css.text().strip(),
            tags=tags
        )
        
        # v3.3: 기존 항목의 메타데이터 보존
        if existing:
            item.is_favorite = existing.is_favorite
            item.test_count = existing.test_count
            item.success_count = existing.success_count
            item.last_tested = existing.last_tested
            item.sort_order = existing.sort_order
            item.is_verified = existing.is_verified
            item.element_tag = existing.element_tag
            item.element_text = existing.element_text
            item.found_window = existing.found_window
            item.found_frame = existing.found_frame
            item.alternatives = list(existing.alternatives or [])
            item.element_attributes = dict(existing.element_attributes or {})
            item.screenshot_path = existing.screenshot_path
            item.ai_generated = existing.ai_generated
        
        # 현재 활성 프레임 정보가 있다면 저장 (테스트 후 저장 시 유용)
        if self.browser.current_frame_path:
             item.found_frame = self.browser.current_frame_path
             
        self.config.add_or_update(item)
        self._table_data_dirty = True
        self._filter_options_dirty = True
        self._refresh_table(refresh_filters=True)
        self._update_undo_redo_actions()  # v4.0
        # 히스토리 현재 상태 동기화 (변경 후)
        self.history_manager.sync_current_state(self.config.items)
        self._show_toast(f"'{name}' 저장 완료", "success")

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

    def _new_config(self):
        if QMessageBox.question(self, "새 설정", "모든 항목을 지우고 초기화하시겠습니까?") == QMessageBox.StandardButton.Yes:
            self.config = SiteConfig.from_preset("빈 템플릿")
            self._table_data_dirty = True
            self._filter_options_dirty = True
            self._refresh_table(refresh_filters=True)
            self._clear_editor()
            self._reset_history_baseline()

    def _open_config(self):
        fname, _ = QFileDialog.getOpenFileName(self, '설정 열기', '', 'JSON 파일 (*.json)')
        if fname:
            try:
                with open(fname, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.config = SiteConfig.from_dict(data)
                    self._table_data_dirty = True
                    self._filter_options_dirty = True
                    self._refresh_table(refresh_filters=True)
                    self._reset_history_baseline()
                    self._show_toast("설정을 불러왔습니다.", "success")
            except Exception as e:
                self._show_toast(f"로드 실패: {e}", "error")

    def _save_config(self):
        fname, _ = QFileDialog.getSaveFileName(self, '설정 저장', f"{self.config.name}.json", 'JSON 파일 (*.json)')
        if fname:
            try:
                with open(fname, 'w', encoding='utf-8') as f:
                    json.dump(self.config.to_dict(), f, indent=2, ensure_ascii=False)
                    self._show_toast("저장되었습니다.", "success")
            except Exception as e:
                self._show_toast(f"저장 실패: {e}", "error")

    def _export(self, fmt):
        """내보내기"""
        if not self.config.items:
            self._show_toast("내보낼 항목이 없습니다.", "warning")
            return
            
        fname, _ = QFileDialog.getSaveFileName(self, f'{fmt.upper()}로 내보내기', f"xpath_export", f'{fmt.upper()} 파일 (*.{fmt})')
        if not fname: return
        
        try:
            if fmt == 'json':
                data = [item.to_dict() for item in self.config.items]
                with open(fname, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            elif fmt == 'csv':
                with open(fname, 'w', encoding='utf-8', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(["이름", "XPath", "카테고리", "설명"])
                    for item in self.config.items:
                        writer.writerow([item.name, item.xpath, item.category, item.description])
            elif fmt == 'python':
                content = "# Selenium XPaths\n\nclass XPaths:\n"
                for item in self.config.items:
                    safe_name = item.name.replace(' ', '_').upper()
                    xpath_literal = json.dumps(item.xpath, ensure_ascii=False)
                    desc_comment = (item.description or "").replace("\n", " ").replace("\r", " ")
                    content += f"    {safe_name} = {xpath_literal}  # {desc_comment}\n"
                with open(fname, 'w', encoding='utf-8') as f:
                    f.write(content)
            elif fmt == 'javascript':
                content = "const XPaths = {\n"
                for item in self.config.items:
                    name_literal = json.dumps(item.name, ensure_ascii=False)
                    xpath_literal = json.dumps(item.xpath, ensure_ascii=False)
                    desc_comment = (item.description or "").replace("\n", " ").replace("\r", " ")
                    content += f"    {name_literal}: {xpath_literal}, // {desc_comment}\n"
                content += "};"
                with open(fname, 'w', encoding='utf-8') as f:
                    f.write(content)
                 
            self._show_toast(f"{fmt.upper()} 내보내기 성공", "success")
             
        except Exception as e:
            self._show_toast(f"내보내기 실패: {e}", "error")

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

    def _show_xpath_history(self):
        """[BUG-005] 히스토리 중복 제거된 목록 표시"""
        history = self._load_xpath_history_data()
        if not history:
            self._show_toast("히스토리가 비어있습니다.", "info")
            return
            
        dialog = QDialog(self)
        dialog.setWindowTitle("XPath 히스토리")
        dialog.resize(600, 400)
        
        layout = QVBoxLayout(dialog)
        
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["날짜", "??", "XPath", "???"])
        history_hh = table.horizontalHeader()
        if history_hh is not None:
            history_hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        
        # 최신순 정렬
        for row_data in reversed(history):
            row = table.rowCount()
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(row_data.get('time', '')))
            table.setItem(row, 1, QTableWidgetItem(row_data.get('tag', '')))
            table.setItem(row, 2, QTableWidgetItem(row_data.get('xpath', '')))
            table.setItem(row, 3, QTableWidgetItem(row_data.get('frame', 'main')))
            
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.doubleClicked.connect(lambda: self._use_history_item(table, dialog))
        
        layout.addWidget(table)
        
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_use = btn_box.addButton("선택 사용", QDialogButtonBox.ButtonRole.AcceptRole)
        btn_clear = btn_box.addButton("모두 지우기", QDialogButtonBox.ButtonRole.ResetRole)
        
        btn_box.rejected.connect(dialog.reject)
        if btn_use is not None:
            btn_use.clicked.connect(lambda: self._use_history_item(table, dialog))
        if btn_clear is not None:
            btn_clear.clicked.connect(lambda: self._clear_history(dialog))
        
        layout.addWidget(btn_box)
        dialog.exec()

    def _add_to_history(self, xpath, css, tag, frame):
        """[BUG-005] 중복 방지하며 히스토리 추가"""
        history = self._load_xpath_history_data()
        
        new_entry = {
            "xpath": xpath,
            "css": css,
            "tag": tag,
            "frame": frame,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # 중복 검사 (최근 10개만 검사해도 충분)
        is_duplicate = False
        for entry in history[-10:]:
            if entry['xpath'] == xpath and entry['frame'] == frame:
                is_duplicate = True
                break
        
        if not is_duplicate:
            history.append(new_entry)
            # 최대 100개 유지
            if len(history) > 100:
                history = history[-100:]
            self._save_xpath_history_data(history)

    def _load_xpath_history_data(self):
        return self.settings.value("xpath_history", [])

    def _save_xpath_history_data(self, history):
        self.settings.setValue("xpath_history", history)

    def _use_history_item(self, table, dialog):
        selected = table.selectedItems()
        if not selected: return
        
        row = selected[0].row()
        xpath = table.item(row, 2).text()
        frame = table.item(row, 3).text()
        
        self.input_xpath.setPlainText(xpath)
        self._show_toast("히스토리에서 불러왔습니다.", "success")
        dialog.accept()

    def _clear_history(self, dialog):
        if QMessageBox.question(dialog, "확인", "히스토리를 모두 삭제하시겠습니까?") == QMessageBox.StandardButton.Yes:
            self._save_xpath_history_data([])
            dialog.reject()
            self._show_toast("히스토리가 삭제되었습니다.", "success")

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

    def _save_cookies(self):
        """쿠키 저장"""
        if not self.browser.is_alive(): return
        driver = self.browser.driver
        if driver is None:
            return
        fname, _ = QFileDialog.getSaveFileName(self, '쿠키 저장', 'cookies.json', 'JSON 파일 (*.json)')
        if fname:
            try:
                cookies = driver.get_cookies()
                with open(fname, 'w', encoding='utf-8') as f:
                    json.dump(cookies, f)
                self._show_toast(f"쿠키 {len(cookies)}개 저장됨", "success")
            except Exception as e:
                self._show_toast(f"실패: {e}", "error")

    def _load_cookies(self):
        """쿠키 로드"""
        if not self.browser.is_alive(): return
        driver = self.browser.driver
        if driver is None:
            return
        fname, _ = QFileDialog.getOpenFileName(self, '쿠키 열기', '', 'JSON 파일 (*.json)')
        if fname:
            try:
                with open(fname, 'r', encoding='utf-8') as f:
                    cookies = json.load(f)
                for cookie in cookies:
                    try:
                        driver.add_cookie(cookie)
                    except Exception:
                        pass  # 개별 쿠키 추가 실패 시 무시
                self._show_toast(f"쿠키 {len(cookies)}개 로드됨", "success")
                driver.refresh()
            except Exception as e:
                self._show_toast(f"실패: {e}", "error")

    def _clear_cookies(self):
        if self.browser.is_alive():
            driver = self.browser.driver
            if driver is None:
                return
            driver.delete_all_cookies()
            self._show_toast("모든 쿠키가 삭제되었습니다.", "success")
