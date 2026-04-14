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


class ExplorerDataHistoryMixin:
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
        table.setHorizontalHeaderLabels(["날짜", "태그", "XPath", "프레임"])
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
        raw = self.settings.value('xpath_history', [])
        if not isinstance(raw, list):
            return []

        normalized: List[Dict[str, Any]] = []
        for row in raw:
            if isinstance(row, dict):
                normalized.append(dict(row))
        return normalized

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
