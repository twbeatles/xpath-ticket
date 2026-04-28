# -*- coding: utf-8 -*-
# pyright: reportAttributeAccessIssue=false, reportCallIssue=false, reportArgumentType=false
"""XPath Explorer mixin module (auto-split from legacy main file)."""

import csv
import json
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from xpath_explorer.qt_compat import (
    QAction,
    QApplication,
    QAbstractItemView,
    QColor,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    Qt,
    QTimer,
    QVBoxLayout,
    QWidget,
)

from xpath_explorer.core.constants import (
    WORKER_WAIT_TIMEOUT,
    category_to_label,
)
from xpath_explorer.core.config import XPathItem
from xpath_explorer.workers.background import (
    PickerWatcher,
    ValidateWorker,
    LivePreviewWorker,
    AIGenerateWorker,
    DiffAnalyzeWorker,
    BatchTestWorker,
    BatchScenarioWorker,
    InstallChromiumWorker,
)
from xpath_explorer.core.perf import perf_span, log_perf_summary
from xpath_explorer.tools.codegen import CodeTemplate, XPathTemplate
from xpath_explorer.browser.dom_export import (
    render_dom_report_htm,
    render_dom_diff_report_htm,
    diff_dom_snapshots,
)

from xpath_explorer.runtime import logger, error_telemetry


class ExplorerPlaywrightToolsMixin:
    def _set_playwright_status_ui(self, connected: bool):
        if connected:
            self.lbl_pw_status.setText("● 연결됨")
            self.lbl_pw_status.setStyleSheet("color: #a6e3a1;")
            self.btn_pw_toggle.setText("Playwright 종료")
        else:
            self.lbl_pw_status.setText("● 미연결")
            self.lbl_pw_status.setStyleSheet("color: #f38ba8;")
            self.btn_pw_toggle.setText("Playwright 시작")

    def _start_playwright_with_navigation(self, url: str) -> bool:
        if self.pw_manager is None:
            return False
        if not self.pw_manager.launch(headless=False, stealth=True):
            return False

        self._set_playwright_status_ui(True)

        if url == "about:blank":
            self._show_toast("Playwright 브라우저가 시작되었습니다.", "success")
            return True

        nav_result = self.pw_manager.navigate(url)
        if nav_result is True:
            self._show_toast("Playwright 브라우저가 시작되었습니다.", "success")
        elif nav_result is None:
            self._show_toast(
                f"Playwright는 연결되었지만 페이지 로딩이 지연되었습니다: {url}",
                "warning",
                4000,
            )
        else:
            self._show_toast(
                f"Playwright는 연결되었지만 페이지 이동에 실패했습니다: {url}",
                "warning",
                4000,
            )
        return True

    def _begin_playwright_chromium_install(self, url: str):
        worker = getattr(self, "playwright_install_worker", None)
        if worker is not None and worker.isRunning():
            self._show_toast("Chromium 설치가 이미 진행 중입니다.", "info")
            return

        from xpath_explorer.mixins import tools_mixin as tools_mixin_module

        self.playwright_install_worker = tools_mixin_module.InstallChromiumWorker()
        worker = self.playwright_install_worker
        self.btn_pw_toggle.setEnabled(False)
        self._show_toast("Chromium 설치 중... (잠시 기다려주세요)", "info", 4000)
        worker.completed.connect(lambda ok, msg, target=url: self._on_playwright_chromium_installed(ok, msg, target))
        worker.start()

    def _on_playwright_chromium_installed(self, success: bool, message: str, url: str):
        self.playwright_install_worker = None
        self.btn_pw_toggle.setEnabled(True)

        if not success:
            detail = f": {message}" if message else ""
            self._show_toast(f"Chromium 설치 실패{detail}", "error", 5000)
            self._set_playwright_status_ui(False)
            return

        self._show_toast("Chromium 설치 완료. Playwright를 다시 시작합니다.", "success", 3000)
        if not self._start_playwright_with_navigation(url):
            last_error = getattr(self.pw_manager, "last_error", "")
            if last_error:
                self._show_toast(f"Playwright 재시작 실패: {last_error}", "error")
            else:
                self._show_toast("Playwright 재시작 실패", "error")
            self._set_playwright_status_ui(False)

    def _toggle_playwright(self):
        """Playwright 브라우저 토글"""
        try:
            from xpath_explorer.browser.playwright import PlaywrightManager

            if self.pw_manager is None:
                self.pw_manager = PlaywrightManager()

            if self.pw_manager.is_alive():
                self.pw_manager.close()
                self._set_playwright_status_ui(False)
                self._show_toast("Playwright 브라우저가 종료되었습니다.", "info")
                return

            url = self.input_url.text().strip() or "about:blank"
            if self._start_playwright_with_navigation(url):
                return

            self._set_playwright_status_ui(False)
            last_error = getattr(self.pw_manager, "last_error", "")
            if last_error:
                self._show_toast(f"Playwright 시작 실패: {last_error}", "error")

            from xpath_explorer.mixins import tools_mixin as tools_mixin_module

            choice = tools_mixin_module.QMessageBox.question(
                self,
                "Playwright 시작 실패",
                "Playwright Chromium이 설치되지 않았거나 실행에 실패했습니다.\n\n"
                "Chromium을 지금 설치하시겠습니까? (playwright install chromium)",
                tools_mixin_module.QMessageBox.StandardButton.Yes
                | tools_mixin_module.QMessageBox.StandardButton.No,
            )
            if choice == tools_mixin_module.QMessageBox.StandardButton.Yes:
                self._begin_playwright_chromium_install(url)
            else:
                self._show_toast("Playwright 시작 실패", "error")
        except ImportError:
            self._show_toast("Playwright가 설치되지 않았습니다. pip install playwright", "error")
        except Exception as e:
            self._show_toast(f"Playwright 오류: {e}", "error")

    def _scan_page_elements(self):
        """Playwright로 페이지 요소 자동 스캔"""
        if not self.pw_manager or not self.pw_manager.is_alive():
            self._show_toast("Playwright 브라우저가 실행되지 않았습니다.", "warning")
            return
        
        scan_label = self.combo_scan_type.currentText()
        scan_type = self.combo_scan_type.currentData()
        if not isinstance(scan_type, str) or not scan_type:
            scan_type = scan_label
        scope_combo = getattr(self, "combo_scan_scope", None)
        scan_scope = "current_frame"
        scope_label = "현재 프레임"
        if scope_combo is not None:
            scope_label = str(scope_combo.currentText() or scope_label)
            combo_scope = scope_combo.currentData()
            if isinstance(combo_scope, str) and combo_scope:
                scan_scope = combo_scope
        self._show_toast(f"{scan_label} 스캔 중... ({scope_label})", "info", 2000)
        
        try:
            with perf_span("ui.scan_page_elements"):
                elements = self.pw_manager.scan_elements(scan_type, max_count=50, scope=scan_scope)
                
                self.table_scan_results.setUpdatesEnabled(False)
                self.table_scan_results.setRowCount(len(elements))
                
                for row, elem in enumerate(elements):
                    xpath = elem.xpath
                    if len(xpath) > 80:
                        xpath = xpath[:77] + "..."
                    self.table_scan_results.setItem(row, 0, QTableWidgetItem(xpath))
                    self.table_scan_results.setItem(row, 1, QTableWidgetItem(elem.tag))
                    text = elem.text[:30] + "..." if len(elem.text) > 30 else elem.text
                    self.table_scan_results.setItem(row, 2, QTableWidgetItem(text))
                    frame_item = QTableWidgetItem(elem.frame_path or "main")
                    frame_item.setToolTip(elem.frame_path or "main")
                    self.table_scan_results.setItem(row, 3, frame_item)
                    window_text = elem.window_title or elem.window_url or elem.window_handle
                    window_item = QTableWidgetItem(window_text)
                    window_item.setToolTip(elem.window_url or window_text)
                    self.table_scan_results.setItem(row, 4, window_item)
                    
                    btn_use = QPushButton("사용")
                    btn_use.setObjectName("success")
                    btn_use.setCursor(Qt.CursorShape.PointingHandCursor)
                    btn_use.clicked.connect(lambda checked, e=elem: self._use_scanned_element(e))
                    self.table_scan_results.setCellWidget(row, 5, btn_use)

                self.table_scan_results.setUpdatesEnabled(True)
                self.lbl_scan_summary.setText(f"스캔된 요소: {len(elements)}개")
                self._show_toast(f"{len(elements)}개의 {scan_label}를 찾았습니다.", "success")
            
        except Exception as e:
            self.table_scan_results.setUpdatesEnabled(True)
            self._show_toast(f"스캔 실패: {e}", "error")

    def _export_dom_playwright_htm(self, scope: str = "all", include_frames: bool = True):
        """현재 Playwright 브라우저의 DOM을 단일 HTM으로 저장."""
        if not self.pw_manager or not self.pw_manager.is_alive():
            self._show_toast("Playwright 브라우저를 먼저 실행하세요.", "warning")
            return

        default_name = f"playwright_dom_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.htm"
        fname, _ = QFileDialog.getSaveFileName(
            self,
            "Playwright DOM 저장",
            default_name,
            "HTM 파일 (*.htm *.html)",
        )
        if not fname:
            return

        if not fname.lower().endswith((".htm", ".html")):
            fname += ".htm"

        scope_label = "현재 창 + iframe" if scope == "current" and include_frames else ("현재 창" if scope == "current" else "전체")
        self._show_toast(f"Playwright DOM 추출 중... ({scope_label})", "info", 2000)
        try:
            snapshots = self.pw_manager.collect_dom_snapshots(include_frames=include_frames, scope=scope)
            current_window = self.pw_manager.get_current_window_metadata()
            report = render_dom_report_htm(
                snapshots,
                source_label="Playwright",
                scope=scope,
                selected_window_title=str(current_window.get("title", "") or ""),
                selected_window_url=str(current_window.get("url", "") or ""),
            )
            with open(fname, "w", encoding="utf-8") as f:
                f.write(report)

            fail_count = sum(1 for s in snapshots if s.error)
            self._show_toast(
                f"DOM 저장 완료: {fname} (문서 {len(snapshots)}개, 실패 {fail_count}개)",
                "success",
                5000,
            )
        except Exception as e:
            logger.error(f"Playwright DOM 저장 실패: {e}")
            self._show_toast(f"DOM 저장 실패: {e}", "error")

    def _use_scanned_element(self, element):
        """스캔된 요소를 편집기로 로드"""
        self.input_xpath.setPlainText(element.xpath)
        self.input_css.setText(element.css_selector)
        self._editing_source_engine = "playwright"
        self._editing_source_frame = str(getattr(element, "frame_path", "") or "main")
        self._editing_source_window = str(getattr(element, "window_handle", "") or "")
        self._editing_source_window_title = str(getattr(element, "window_title", "") or "")
        self._editing_source_window_url = str(getattr(element, "window_url", "") or "")
        
        # 자동 이름 생성 (태그 + ID 또는 이름)
        if element.element_id:
            suggested_name = element.element_id
        elif element.element_name:
            suggested_name = element.element_name
        else:
            suggested_name = f"{element.tag}_{len(self.config.items) + 1}"
        
        self.input_name.setText(suggested_name)
        self.input_desc.setText(element.text[:50] if element.text else "")
        
        self._show_toast(f"'{suggested_name}' 요소를 로드했습니다.", "success")
        
        # Playwright에서 하이라이트
        if self.pw_manager and self.pw_manager.is_alive():
            frame_path = str(getattr(element, "frame_path", "") or "")
            if frame_path and frame_path != "main":
                self.pw_manager.switch_to_frame(frame_path)
            self.pw_manager.highlight(element.xpath, 2000)
