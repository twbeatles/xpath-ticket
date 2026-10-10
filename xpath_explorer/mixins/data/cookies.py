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

from pathlib import Path

from xpath_explorer.core.constants import APP_TITLE, SITE_PRESETS, category_to_label, category_to_value
from xpath_explorer.core.config import XPathItem, SiteConfig
from xpath_explorer.core.cookie_safety import partition_cookies_for_url
from xpath_explorer.core.paths import atomic_write_json
from xpath_explorer.core.perf import perf_span


class ExplorerDataCookiesMixin:
    def _cookie_engine(self):
        """Return (kind, engine) for cookie work: Selenium first, then Playwright."""
        browser = getattr(self, "browser", None)
        if browser is not None:
            try:
                if browser.is_alive():
                    return "selenium", browser
            except Exception:
                pass
        pw_manager = getattr(self, "pw_manager", None)
        if pw_manager is not None:
            try:
                if pw_manager.is_alive():
                    return "playwright", pw_manager
            except Exception:
                pass
        return None, None

    def _save_cookies(self):
        """쿠키 저장 (Selenium 우선, 없으면 Playwright 세션)."""
        kind, engine = self._cookie_engine()
        if engine is None:
            return
        if kind == "selenium":
            driver = engine.driver
            if driver is None:
                return
        reply = QMessageBox.warning(
            self,
            "쿠키 저장",
            "로그인 세션이 포함된 쿠키가 암호화 없이 JSON 파일로 저장됩니다. 계속할까요?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        fname, _ = QFileDialog.getSaveFileName(self, '쿠키 저장', 'cookies.json', 'JSON 파일 (*.json)')
        if fname:
            try:
                if kind == "selenium":
                    cookies = driver.get_cookies()
                else:
                    cookies = engine.get_cookies()
                atomic_write_json(Path(fname), cookies, backup=False)
                try:
                    Path(fname).chmod(0o600)
                except Exception:
                    pass
                self._show_toast(f"쿠키 {len(cookies)}개 저장됨", "success")
            except Exception as e:
                self._show_toast(f"실패: {e}", "error")

    def _report_cookie_load(self, total: int, success_count: int, failures: Counter) -> None:
        fail_count = max(0, total - success_count)
        if fail_count > 0:
            top_failures = ', '.join(
                f'{label}({count})' for label, count in failures.most_common(3)
            )
            summary = f'Cookie load complete: success {success_count}, failed {fail_count}'
            if top_failures:
                summary += f' | Top failures: {top_failures}'
            self._show_toast(summary, 'warning', 5000)
        else:
            self._show_toast(f'Cookie load complete: {success_count}', 'success')

    def _load_cookies(self):
        """Load cookies from JSON and report success/failure counts.

        Selenium 우선, 없으면 Playwright 세션에 주입한다.
        """
        kind, engine = self._cookie_engine()
        if engine is None:
            return
        if kind == "selenium":
            driver = engine.driver
            if driver is None:
                return
        fname, _ = QFileDialog.getOpenFileName(self, 'Open Cookies', '', 'JSON Files (*.json)')
        if fname:
            try:
                with open(fname, 'r', encoding='utf-8') as f:
                    cookies = json.load(f)
                if not isinstance(cookies, list):
                    self._show_toast('Invalid cookie file format.', 'error')
                    return

                if kind == "selenium":
                    try:
                        page_url = str(driver.current_url or "")
                    except Exception:
                        page_url = ""
                else:
                    try:
                        page_url = str((engine.get_current_window_metadata() or {}).get("url", "") or "")
                    except Exception:
                        page_url = ""
                accepted, rejected = partition_cookies_for_url(cookies, page_url)

                success_count = 0
                failures: Counter[str] = Counter()
                for cookie in rejected:
                    key = ''
                    if isinstance(cookie, dict):
                        key = str(cookie.get('name', '') or cookie.get('domain', ''))
                    failures[key or 'domain-mismatch'] += 1
                for cookie in accepted:
                    try:
                        if kind == "selenium":
                            driver.add_cookie(cookie)
                        else:
                            engine.set_cookies([cookie])
                        success_count += 1
                    except Exception:
                        key = str(cookie.get('name', '') or cookie.get('domain', ''))
                        failures[key or 'unknown'] += 1

                self._report_cookie_load(len(cookies), success_count, failures)

                if kind == "selenium":
                    driver.refresh()
                else:
                    try:
                        reloader = getattr(engine, "reload_current_page", None)
                        if callable(reloader):
                            reloader()
                    except Exception:
                        pass
            except Exception as e:
                self._show_toast(f'Failure: {e}', 'error')

    def _clear_cookies(self):
        kind, engine = self._cookie_engine()
        if engine is None:
            return
        if kind == "selenium":
            driver = engine.driver
            if driver is None:
                return
            driver.delete_all_cookies()
        else:
            try:
                engine.clear_cookies()
            except Exception as e:
                self._show_toast(f"실패: {e}", "error")
                return
        self._show_toast("모든 쿠키가 삭제되었습니다.", "success")
