# -*- coding: utf-8 -*-
# pyright: reportAttributeAccessIssue=false, reportCallIssue=false, reportArgumentType=false
"""XPath Explorer mixin module (auto-split from legacy main file)."""

import csv
import io
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
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
from xpath_explorer.core.config_state import config_fingerprint, is_config_dirty
from xpath_explorer.core.perf import perf_span
from xpath_explorer.core.paths import atomic_write_json, atomic_write_text
from xpath_explorer.tools.csv_safety import sanitize_csv_value


def _safe_config_filename(name: str) -> str:
    """Strip path separators/control chars for the save-dialog default name."""
    safe = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", name or "").strip().strip(".")
    return safe or "xpath_config"


class ExplorerDataFilesMixin:
    def _mark_config_clean(self):
        self._saved_config_fingerprint = config_fingerprint(self.config)

    def _autosave_snapshot(self):
        """Best-effort crash-recovery snapshot after structural edits."""
        try:
            from xpath_explorer.core import autosave as autosave_module

            autosave_module.write_autosave(self.config)
        except Exception:
            pass

    def _clear_autosave(self):
        try:
            from xpath_explorer.core import autosave as autosave_module

            autosave_module.clear_autosave()
        except Exception:
            pass

    def _maybe_restore_autosave(self):
        """Offer to restore an autosave left by a session that never saved."""
        try:
            from xpath_explorer.core import autosave as autosave_module

            payload = autosave_module.read_autosave()
            if payload is None:
                return
            if not autosave_module.is_autosave_restorable(self.config, payload):
                autosave_module.clear_autosave()
                return
            reply = QMessageBox.question(
                self,
                "작업 복원",
                "이전에 저장하지 않고 끝난 작업이 있습니다.\n복원할까요?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply != QMessageBox.StandardButton.Yes:
                autosave_module.clear_autosave()
                return
            try:
                restored = SiteConfig.from_dict(payload.get("config") or {})
            except Exception as e:
                autosave_module.clear_autosave()
                self._show_toast(f"자동 저장 복원 실패: {e}", "error")
                return
            self.config = restored
            self._editing_original_name = ''
            self._table_data_dirty = True
            self._filter_options_dirty = True
            self._refresh_table(refresh_filters=True)
            self._reset_history_baseline()
            self._show_toast("이전 작업을 복원했습니다. 저장(Ctrl+S)하세요.", "success")
        except Exception:
            pass

    def _is_config_dirty(self) -> bool:
        return is_config_dirty(self.config, getattr(self, "_saved_config_fingerprint", None))

    def _confirm_discard_unsaved(self, action_label: str = "계속") -> bool:
        if not self._is_config_dirty():
            return True
        reply = QMessageBox.question(
            self,
            "저장되지 않은 변경",
            f"저장하지 않은 XPath 목록이 있습니다.\n{action_label}하기 전에 저장할까요?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if reply == QMessageBox.StandardButton.Cancel:
            return False
        if reply == QMessageBox.StandardButton.Save:
            self._save_config()
            return not self._is_config_dirty()
        return True

    def _new_config(self):
        if not self._confirm_discard_unsaved("새 설정"):
            return
        if QMessageBox.question(self, "새 설정", "모든 항목을 지우고 초기화하시겠습니까?") == QMessageBox.StandardButton.Yes:
            self.config = SiteConfig.from_preset("빈 템플릿")
            self._editing_original_name = ''
            self._table_data_dirty = True
            self._filter_options_dirty = True
            self._refresh_table(refresh_filters=True)
            self._clear_editor()
            self._reset_history_baseline()
            self._mark_config_clean()
            self._clear_autosave()

    def _open_config(self):
        if not self._confirm_discard_unsaved("설정 열기"):
            return
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
                    self._mark_config_clean()
                    self._clear_autosave()
                    self._show_toast("설정을 불러왔습니다.", "success")
            except Exception as e:
                self._show_toast(f"로드 실패: {e}", "error")

    def _save_config(self):
        fname, _ = QFileDialog.getSaveFileName(self, '설정 저장', f"{_safe_config_filename(self.config.name)}.json", 'JSON 파일 (*.json)')
        if fname:
            try:
                atomic_write_json(Path(fname), self.config.to_dict())
                self._mark_config_clean()
                self._clear_autosave()
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
                atomic_write_json(Path(fname), data)
            elif fmt == 'csv':
                buffer = io.StringIO(newline='')
                writer = csv.writer(buffer)
                writer.writerow(['이름', 'XPath', '카테고리', '설명'])
                for item in self.config.items:
                    writer.writerow([
                        sanitize_csv_value(item.name),
                        sanitize_csv_value(item.xpath),
                        sanitize_csv_value(item.category),
                        sanitize_csv_value(item.description),
                    ])
                atomic_write_text(Path(fname), buffer.getvalue())
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
                atomic_write_text(Path(fname), content)
            elif fmt == 'javascript':
                content = 'const XPaths = {\n'
                for item in self.config.items:
                    name_literal = json.dumps(item.name, ensure_ascii=False)
                    xpath_literal = json.dumps(item.xpath, ensure_ascii=False)
                    desc_comment = (item.description or '').replace('\n', ' ').replace('\r', ' ')
                    content += f'    {name_literal}: {xpath_literal}, // {desc_comment}\n'
                content += '};'
                atomic_write_text(Path(fname), content)

            self._show_toast(f'{fmt.upper()} 내보내기 성공', 'success')

        except Exception as e:
            self._show_toast(f'내보내기 실패: {e}', 'error')
