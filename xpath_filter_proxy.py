# -*- coding: utf-8 -*-
"""
XPath item filter proxy model.
"""

from PyQt6.QtCore import QSortFilterProxyModel, QModelIndex

from xpath_table_model import XPathItemTableModel


class XPathFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._search_text = ""
        self._category_filter = ""
        self._all_category_value = ""
        self._favorites_only = False
        self._tag_filter = ""
        self._all_tag_value = ""

    def set_search_text(self, text: str):
        text = (text or "").strip().lower()
        if self._search_text == text:
            return
        self._search_text = text
        self.invalidateFilter()

    def set_category_filter(self, category: str, all_value: str):
        category = category or all_value or ""
        all_value = all_value or ""
        if self._category_filter == category and self._all_category_value == all_value:
            return
        self._category_filter = category
        self._all_category_value = all_value
        self.invalidateFilter()

    def set_favorites_only(self, favorites_only: bool):
        favorites_only = bool(favorites_only)
        if self._favorites_only == favorites_only:
            return
        self._favorites_only = favorites_only
        self.invalidateFilter()

    def set_tag_filter(self, tag: str, all_value: str):
        tag = tag or all_value or ""
        all_value = all_value or ""
        if self._tag_filter == tag and self._all_tag_value == all_value:
            return
        self._tag_filter = tag
        self._all_tag_value = all_value
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        model = self.sourceModel()
        if not isinstance(model, XPathItemTableModel):
            return True

        item = model.get_item(source_row)
        if item is None:
            return False

        if (
            self._category_filter
            and self._all_category_value
            and self._category_filter != self._all_category_value
            and item.category != self._category_filter
        ):
            return False

        if self._favorites_only and not item.is_favorite:
            return False

        if (
            self._tag_filter
            and self._all_tag_value
            and self._tag_filter != self._all_tag_value
            and self._tag_filter not in item.tags
        ):
            return False

        if self._search_text:
            search_index = model.index(source_row, XPathItemTableModel.COLUMN_NAME, source_parent)
            haystack = model.data(search_index, XPathItemTableModel.ROLE_SEARCH_TEXT) or ""
            if self._search_text not in haystack:
                return False

        return True

    def get_item(self, proxy_row: int):
        model = self.sourceModel()
        if not isinstance(model, XPathItemTableModel):
            return None
        proxy_index = self.index(proxy_row, 0)
        if not proxy_index.isValid():
            return None
        source_index = self.mapToSource(proxy_index)
        if not source_index.isValid():
            return None
        return model.get_item(source_index.row())

