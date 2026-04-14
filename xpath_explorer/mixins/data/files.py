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


class ExplorerDataFilesMixin:
    def _new_config(self):
        if QMessageBox.question(self, "새 설정", "모든 항목을 지우고 초기화하시겠습니까?") == QMessageBox.StandardButton.Yes:
            self.config = SiteConfig.from_preset("빈 템플릿")
            self._editing_original_name = ''
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
                    self._editing_original_name = ''
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
            self._show_toast('내보낼 항목이 없습니다.', 'warning')
            return

        fname, _ = QFileDialog.getSaveFileName(self, f'{fmt.upper()}로 내보내기', 'xpath_export', f'{fmt.upper()} 파일 (*.{fmt})')
        if not fname:
            return

        try:
            if fmt == 'json':
                data = [item.to_dict() for item in self.config.items]
                with open(fname, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            elif fmt == 'csv':
                with open(fname, 'w', encoding='utf-8', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['이름', 'XPath', '카테고리', '설명'])
                    for item in self.config.items:
                        writer.writerow([item.name, item.xpath, item.category, item.description])
            elif fmt == 'python':
                content = '# Selenium XPaths\n\nclass XPaths:\n'
                used_names: Dict[str, int] = {}
                for item in self.config.items:
                    raw_safe_name = self.code_generator._safe_var_name(item.name)
                    suffix = used_names.get(raw_safe_name, 0)
                    used_names[raw_safe_name] = suffix + 1
                    safe_name = raw_safe_name if suffix == 0 else f'{raw_safe_name}_{suffix + 1}'
                    xpath_literal = json.dumps(item.xpath, ensure_ascii=False)
                    desc_comment = (item.description or '').replace('\n', ' ').replace('\r', ' ')
                    content += f'    {safe_name} = {xpath_literal}  # {desc_comment}\n'
                compile(content, '<xpath_export>', 'exec')
                with open(fname, 'w', encoding='utf-8') as f:
                    f.write(content)
            elif fmt == 'javascript':
                content = 'const XPaths = {\n'
                for item in self.config.items:
                    name_literal = json.dumps(item.name, ensure_ascii=False)
                    xpath_literal = json.dumps(item.xpath, ensure_ascii=False)
                    desc_comment = (item.description or '').replace('\n', ' ').replace('\r', ' ')
                    content += f'    {name_literal}: {xpath_literal}, // {desc_comment}\n'
                content += '};'
                with open(fname, 'w', encoding='utf-8') as f:
                    f.write(content)

            self._show_toast(f'{fmt.upper()} 내보내기 성공', 'success')

        except Exception as e:
            self._show_toast(f'내보내기 실패: {e}', 'error')
