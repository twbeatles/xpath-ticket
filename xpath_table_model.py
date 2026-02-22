# -*- coding: utf-8 -*-
"""
XPath item table model (Model/View optimization).
"""

from typing import Dict, List, Optional

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PyQt6.QtGui import QColor

from xpath_config import XPathItem
from xpath_constants import category_to_label


class XPathItemTableModel(QAbstractTableModel):
    COLUMN_FAVORITE = 0
    COLUMN_STATUS = 1
    COLUMN_NAME = 2
    COLUMN_CATEGORY = 3
    COLUMN_DESCRIPTION = 4
    COLUMN_SUCCESS_RATE = 5
    COLUMN_DELETE = 6

    HEADERS = ["⭐", "", "이름", "카테고리", "설명", "성공률", ""]

    ROLE_ITEM_NAME = int(Qt.ItemDataRole.UserRole) + 1
    ROLE_SEARCH_TEXT = int(Qt.ItemDataRole.UserRole) + 2

    def __init__(self, items: Optional[List[XPathItem]] = None, parent=None):
        super().__init__(parent)
        self._items: List[XPathItem] = []
        self._name_to_row: Dict[str, int] = {}
        self._search_cache: Dict[str, str] = {}
        self.set_items(items or [])

    def rowCount(self, parent=QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._items)

    def columnCount(self, parent=QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self.HEADERS)

    def headerData(self, section: int, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal and 0 <= section < len(self.HEADERS):
            return self.HEADERS[section]
        return None

    def flags(self, index: QModelIndex):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = index.row()
        if row < 0 or row >= len(self._items):
            return None

        item = self._items[row]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == self.COLUMN_FAVORITE:
                return "⭐" if item.is_favorite else "☆"
            if col == self.COLUMN_STATUS:
                return "✅" if item.is_verified else "❌"
            if col == self.COLUMN_NAME:
                return item.name
            if col == self.COLUMN_CATEGORY:
                return category_to_label(item.category)
            if col == self.COLUMN_DESCRIPTION:
                if item.tags:
                    return f"{item.description} [{', '.join(item.tags)}]"
                return item.description
            if col == self.COLUMN_SUCCESS_RATE:
                return f"{item.success_rate:.0f}%" if item.test_count > 0 else "-"
            if col == self.COLUMN_DELETE:
                return "🗑"

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col in (
                self.COLUMN_FAVORITE,
                self.COLUMN_STATUS,
                self.COLUMN_CATEGORY,
                self.COLUMN_SUCCESS_RATE,
                self.COLUMN_DELETE,
            ):
                return int(Qt.AlignmentFlag.AlignCenter)

        if role == Qt.ItemDataRole.ForegroundRole:
            if col == self.COLUMN_SUCCESS_RATE and item.test_count > 0:
                if item.success_rate >= 80:
                    return QColor("#a6e3a1")
                if item.success_rate >= 50:
                    return QColor("#fab387")
                return QColor("#f38ba8")
            if col == self.COLUMN_DELETE:
                return QColor("#f38ba8")

        if role == Qt.ItemDataRole.BackgroundRole and col == self.COLUMN_CATEGORY:
            return QColor("#313244")

        if role == Qt.ItemDataRole.ToolTipRole:
            if col == self.COLUMN_FAVORITE:
                return "클릭해서 즐겨찾기 토글"
            if col == self.COLUMN_DELETE:
                return "항목 삭제"
            if col == self.COLUMN_DESCRIPTION and item.tags:
                return ", ".join(item.tags)

        if role == self.ROLE_ITEM_NAME:
            return item.name

        if role == self.ROLE_SEARCH_TEXT:
            cached = self._search_cache.get(item.name)
            if cached is None:
                cached = " ".join(
                    [
                        item.name.lower(),
                        item.description.lower(),
                        item.xpath.lower(),
                        " ".join(t.lower() for t in item.tags),
                    ]
                )
                self._search_cache[item.name] = cached
            return cached

        return None

    def set_items(self, items: List[XPathItem]):
        self.beginResetModel()
        self._items = sorted(list(items), key=lambda x: x.sort_order)
        self._rebuild_indexes()
        self.endResetModel()

    def _rebuild_indexes(self):
        self._name_to_row = {item.name: idx for idx, item in enumerate(self._items)}
        self._search_cache.clear()

    def get_item(self, row: int) -> Optional[XPathItem]:
        if 0 <= row < len(self._items):
            return self._items[row]
        return None

    def row_for_name(self, item_name: str) -> Optional[int]:
        row = self._name_to_row.get(item_name)
        if row is not None and 0 <= row < len(self._items):
            if self._items[row].name == item_name:
                return row
        self._rebuild_indexes()
        return self._name_to_row.get(item_name)

    def notify_item_changed(self, item_name: str):
        row = self.row_for_name(item_name)
        if row is None:
            return
        self._search_cache.pop(item_name, None)
        left = self.index(row, 0)
        right = self.index(row, self.columnCount() - 1)
        self.dataChanged.emit(left, right)
