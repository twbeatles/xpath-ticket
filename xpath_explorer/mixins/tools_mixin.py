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

from xpath_constants import (
    APP_TITLE, APP_VERSION, SITE_PRESETS,
    BROWSER_CHECK_INTERVAL, SEARCH_DEBOUNCE_MS,
    LIVE_PREVIEW_DEBOUNCE_MS, WORKER_WAIT_TIMEOUT,
)
from xpath_styles import STYLE
from xpath_config import XPathItem, SiteConfig
from xpath_widgets import ToastWidget, NoWheelComboBox, AnimatedStatusIndicator, IconButton, CollapsibleBox
from xpath_browser import BrowserManager
from xpath_workers import (
    PickerWatcher, ValidateWorker, LivePreviewWorker,
    AIGenerateWorker, DiffAnalyzeWorker, BatchTestWorker,
)
from xpath_perf import perf_span, log_perf_summary
from xpath_codegen import CodeGenerator, CodeTemplate
from xpath_statistics import StatisticsManager
from xpath_optimizer import XPathOptimizer, XPathAlternative
from xpath_history import HistoryManager
from xpath_ai import XPathAIAssistant
from xpath_diff import XPathDiffAnalyzer
from xpath_table_model import XPathItemTableModel
from xpath_filter_proxy import XPathFilterProxyModel

from xpath_explorer.runtime import logger


class ExplorerToolsMixin:
    def _batch_test(self, category: Optional[str] = None):
        """배치 테스트 실행 (취소 가능, 비동기)"""
        if not self.browser.is_alive():
            self._show_toast("브라우저를 먼저 연결해주세요.", "warning")
            return

        if self.batch_worker and self.batch_worker.isRunning():
            self._show_toast("이미 배치 테스트가 실행 중입니다.", "warning")
            return
        
        # 테스트할 항목 필터링
        items_to_test = self.config.items
        if category and category != "전체":
            items_to_test = [i for i in items_to_test if i.category == category]
        
        if not items_to_test:
            self._show_toast("테스트할 항목이 없습니다.", "warning")
            return
        
        self._show_toast(f"{len(items_to_test)}개 항목 배치 테스트 시작...", "info")

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("테스트 준비 중...")
        self.btn_open.setEnabled(False)  # 브라우저 버튼 비활성화
        self.batch_worker = BatchTestWorker(self.browser, list(items_to_test))
        self.batch_worker.progress.connect(self._on_batch_test_progress)
        self.batch_worker.item_tested.connect(self._on_batch_item_tested)
        self.batch_worker.completed.connect(self._on_batch_test_completed)
        self.batch_worker.start()

    def _on_batch_test_progress(self, value: int, message: str):
        self.progress_bar.setValue(value)
        self.progress_bar.setFormat(f"{message} - ESC로 취소")

    def _on_batch_item_tested(self, name: str, success: bool, xpath: str, msg: str):
        self._record_validation_outcome(
            name=name,
            xpath=xpath,
            success=success,
            result={
                'found': success,
                'msg': msg,
            },
        )

    def _on_batch_test_completed(self, results: list, cancelled: bool):
        self.progress_bar.setVisible(False)
        self.progress_bar.setFormat("%p%")
        self.btn_open.setEnabled(True)
        self.batch_worker = None
        self._refresh_table()
        if cancelled:
            self._show_toast("배치 테스트가 취소되었습니다.", "warning")
        if results:
            self._show_batch_report(results, cancelled=cancelled)

    def _batch_test_dialog(self):
        """카테고리 선택 후 배치 테스트"""
        categories = ["전체"] + sorted(self.config.get_categories())
        
        from PyQt6.QtWidgets import QInputDialog
        category, ok = QInputDialog.getItem(
            self, "배치 테스트", "테스트할 카테고리 선택:",
            categories, 0, False
        )
        if ok and category is not None:
            self._batch_test(category)

    def _show_batch_report(self, results: list, cancelled: bool = False):
        """배치 테스트 결과 리포트"""
        dialog = QDialog(self)
        title = "배치 테스트 결과" + (" (취소됨)" if cancelled else "")
        dialog.setWindowTitle(title)
        dialog.resize(700, 500)
        
        layout = QVBoxLayout(dialog)
        
        # 요약
        total = len(results)
        success_count = sum(1 for r in results if r['success'])
        success_rate = (success_count / total * 100) if total > 0 else 0
        
        cancelled_text = " ⚠️ (중도 취소됨)" if cancelled else ""
        summary = QLabel(f"총 {total}개 테스트 | ✅ 성공: {success_count} | ❌ 실패: {total - success_count} | 성공률: {success_rate:.1f}%{cancelled_text}")
        summary.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px;")
        layout.addWidget(summary)
        
        # 결과 테이블
        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["상태", "이름", "결과"])
        batch_hh = table.horizontalHeader()
        if batch_hh is not None:
            batch_hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        
        for r in results:
            row = table.rowCount()
            table.insertRow(row)
            
            status = QTableWidgetItem("✅" if r['success'] else "❌")
            status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, 0, status)
            table.setItem(row, 1, QTableWidgetItem(r['name']))
            table.setItem(row, 2, QTableWidgetItem(r['msg'] if not r['success'] else "Found"))
        
        layout.addWidget(table)
        
        # 닫기 버튼
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_box.rejected.connect(dialog.reject)
        layout.addWidget(btn_box)
        
        dialog.exec()

    def _show_macro_generator(self):
        """매크로 생성 다이얼로그"""
        if not self.config.items:
            self._show_toast("생성할 XPath 항목이 없습니다.", "warning")
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("매크로 코드 생성")
        dialog.resize(800, 600)
        
        layout = QVBoxLayout(dialog)
        
        # 템플릿 선택
        layout.addWidget(QLabel("코드 템플릿:"))
        combo_template = QComboBox()
        combo_template.addItems(["Selenium (파이썬)", "Playwright (파이썬)", "PyAutoGUI"])
        layout.addWidget(combo_template)
        
        # 코드 미리보기
        layout.addWidget(QLabel("생성된 코드:"))
        txt_code = QPlainTextEdit()
        txt_code.setReadOnly(True)
        txt_code.setStyleSheet("font-family: 'Consolas', monospace; background-color: #181825;")
        layout.addWidget(txt_code)
        
        def generate_code():
            template_map = {
                0: CodeTemplate.SELENIUM_PYTHON,
                1: CodeTemplate.PLAYWRIGHT_PYTHON,
                2: CodeTemplate.PYAUTOGUI
            }
            template = template_map.get(combo_template.currentIndex(), CodeTemplate.SELENIUM_PYTHON)
            try:
                code = self.code_generator.generate(self.config.items, template)
            except Exception as e:
                txt_code.setPlainText(f"# 코드 생성 실패\n# {e}")
                self._show_toast(f"코드 생성 실패: {e}", "error")
                return
            txt_code.setPlainText(code)
        
        combo_template.currentIndexChanged.connect(generate_code)
        generate_code()  # 초기 생성
        
        # 버튼
        btn_layout = QHBoxLayout()
        
        btn_copy = QPushButton("📋 복사")
        def copy_code():
            clipboard = QApplication.clipboard()
            if clipboard is not None:
                clipboard.setText(txt_code.toPlainText())
            self._show_toast("코드가 클립보드에 복사되었습니다.", "success")
        btn_copy.clicked.connect(copy_code)
        btn_layout.addWidget(btn_copy)
        
        btn_save = QPushButton("💾 파일로 저장")
        def save_code():
            ext = ".py" if combo_template.currentIndex() < 2 else ".py"
            fname, _ = QFileDialog.getSaveFileName(dialog, "코드 저장", "macro_script", "파이썬 파일 (*.py)")
            if fname:
                with open(fname, 'w', encoding='utf-8') as f:
                    f.write(txt_code.toPlainText())
                self._show_toast(f"저장 완료: {fname}", "success")
        btn_save.clicked.connect(save_code)
        btn_layout.addWidget(btn_save)
        
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(dialog.reject)
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)
        dialog.exec()

    def _show_network_analyzer(self):
        """네트워크 분석 다이얼로그"""
        try:
            from xpath_playwright import NetworkAnalyzer
        except ImportError:
            self._show_toast("Playwright 모듈을 찾을 수 없습니다.", "error")
            return
        
        analyzer = NetworkAnalyzer()
        if not analyzer.is_playwright_available():
            QMessageBox.warning(
                self, "Playwright 필요",
                "네트워크 분석 기능을 사용하려면 Playwright가 필요합니다.\n\n"
                "설치 방법:\n"
                "pip install playwright\n"
                "playwright install chromium"
            )
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("🌐 네트워크 분석")
        dialog.resize(900, 600)
        
        layout = QVBoxLayout(dialog)
        
        # 상태 및 컨트롤
        ctrl_layout = QHBoxLayout()
        
        lbl_status = QLabel("● 대기 중")
        ctrl_layout.addWidget(lbl_status)
        
        input_url = QLineEdit()
        input_url.setPlaceholderText("분석할 URL 입력...")
        input_url.setText(self.config.url or "https://")
        ctrl_layout.addWidget(input_url, 2)
        
        btn_start = QPushButton("🚀 캡처 시작")
        btn_stop = QPushButton("⏹ 중지")
        btn_stop.setEnabled(False)
        
        ctrl_layout.addWidget(btn_start)
        ctrl_layout.addWidget(btn_stop)
        
        layout.addLayout(ctrl_layout)
        
        # 결과 테이블
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["Method", "Status", "Type", "Size", "URL"])
        network_hh = table.horizontalHeader()
        if network_hh is not None:
            network_hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(table)
        
        # 이벤트 핸들러
        def start_capture():
            url = input_url.text().strip()
            if not url:
                return
            
            lbl_status.setText("● 브라우저 시작 중...")
            
            if analyzer.start_browser(url, headless=False):
                analyzer.start_capture()
                lbl_status.setText("● 캡처 중... (페이지 조작 후 중지)")
                lbl_status.setStyleSheet("color: #a6e3a1;")
                btn_start.setEnabled(False)
                btn_stop.setEnabled(True)
            else:
                last_error = getattr(analyzer, "last_error", "")
                if last_error:
                    lbl_status.setText(f"● 시작 실패: {last_error}")
                    self._show_toast(f"네트워크 분석기 시작 실패: {last_error}", "error")
                else:
                    lbl_status.setText("● 시작 실패")
                lbl_status.setStyleSheet("color: #f38ba8;")
        
        def stop_capture():
            requests = analyzer.stop_capture()
            analyzer.close()
            
            lbl_status.setText(f"● 완료 ({len(requests)}개 요청)")
            lbl_status.setStyleSheet("color: #89b4fa;")
            btn_start.setEnabled(True)
            btn_stop.setEnabled(False)
            
            # 테이블 채우기
            table.setRowCount(0)
            for req in requests:
                row = table.rowCount()
                table.insertRow(row)
                table.setItem(row, 0, QTableWidgetItem(req.method))
                table.setItem(row, 1, QTableWidgetItem(str(req.status)))
                table.setItem(row, 2, QTableWidgetItem(req.resource_type))
                table.setItem(row, 3, QTableWidgetItem(f"{req.response_size}"))
                table.setItem(row, 4, QTableWidgetItem(req.url[:100]))
        
        btn_start.clicked.connect(start_capture)
        btn_stop.clicked.connect(stop_capture)
        
        # 닫기 시 정리
        def on_close():
            analyzer.close()
            dialog.reject()
        
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(on_close)
        layout.addWidget(btn_close)
        
        dialog.exec()

    def _show_statistics(self):
        """통계 대시보드"""
        dialog = QDialog(self)
        dialog.setWindowTitle("📈 테스트 통계")
        dialog.resize(700, 500)
        
        layout = QVBoxLayout(dialog)
        
        # 전체 요약
        summary = self.stats_manager.get_summary()
        summary_text = (
            f"총 항목: {summary['total_items']}개 | "
            f"총 테스트: {summary['total_tests']}회 | "
            f"평균 성공률: {summary['average_success_rate']:.1f}%"
        )
        lbl_summary = QLabel(summary_text)
        lbl_summary.setStyleSheet("font-size: 15px; font-weight: bold; padding: 10px;")
        layout.addWidget(lbl_summary)
        
        # 탭 위젯
        tabs = QTabWidget()
        
        # 탭 1: 항목별 통계
        tab_items = QWidget()
        tab_items_layout = QVBoxLayout(tab_items)
        
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["이름", "총 테스트", "성공", "실패", "성공률"])
        stats_hh = table.horizontalHeader()
        if stats_hh is not None:
            stats_hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        
        for item in self.config.items:
            if item.test_count > 0:
                row = table.rowCount()
                table.insertRow(row)
                table.setItem(row, 0, QTableWidgetItem(item.name))
                table.setItem(row, 1, QTableWidgetItem(str(item.test_count)))
                table.setItem(row, 2, QTableWidgetItem(str(item.success_count)))
                table.setItem(row, 3, QTableWidgetItem(str(item.test_count - item.success_count)))
                
                rate_item = QTableWidgetItem(f"{item.success_rate:.0f}%")
                if item.success_rate >= 80:
                    rate_item.setForeground(QColor("#a6e3a1"))
                elif item.success_rate < 50:
                    rate_item.setForeground(QColor("#f38ba8"))
                table.setItem(row, 4, rate_item)
        
        tab_items_layout.addWidget(table)
        tabs.addTab(tab_items, "항목별 통계")
        
        # 탭 2: 불안정 항목
        tab_unstable = QWidget()
        tab_unstable_layout = QVBoxLayout(tab_unstable)
        
        unstable_items = self.stats_manager.get_unstable_items(80)
        if unstable_items:
            list_unstable = QListWidget()
            for stat in unstable_items:
                list_unstable.addItem(f"❌ {stat.name} - 성공률: {stat.success_rate:.0f}% ({stat.total_tests}회)")
            tab_unstable_layout.addWidget(list_unstable)
        else:
            tab_unstable_layout.addWidget(QLabel("불안정한 항목이 없습니다. 👍"))
        
        tabs.addTab(tab_unstable, "불안정 항목")
        
        layout.addWidget(tabs)
        
        # 버튼
        btn_layout = QHBoxLayout()
        
        btn_clear = QPushButton("🗑 통계 초기화")
        btn_clear.clicked.connect(lambda: (
            self.stats_manager.clear_statistics(),
            self._show_toast("통계가 초기화되었습니다.", "success"),
            dialog.reject()
        ))
        btn_layout.addWidget(btn_clear)
        
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(dialog.reject)
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)
        
        dialog.exec()

    def _toggle_playwright(self):
        """Playwright 브라우저 토글"""
        try:
            from xpath_playwright import PlaywrightManager
            
            if self.pw_manager is None:
                self.pw_manager = PlaywrightManager()
            
            if self.pw_manager.is_alive():
                self.pw_manager.close()
                self.lbl_pw_status.setText("● 미연결")
                self.lbl_pw_status.setStyleSheet("color: #f38ba8;")
                self.btn_pw_toggle.setText("Playwright 시작")
                self._show_toast("Playwright 브라우저가 종료되었습니다.", "info")
            else:
                url = self.input_url.text().strip() or "about:blank"
                if self.pw_manager.launch(headless=False, stealth=True):
                    if url != "about:blank":
                        self.pw_manager.navigate(url)
                    self.lbl_pw_status.setText("● 연결됨")
                    self.lbl_pw_status.setStyleSheet("color: #a6e3a1;")
                    self.btn_pw_toggle.setText("Playwright 종료")
                    self._show_toast("Playwright 브라우저가 시작되었습니다.", "success")
                else:
                    last_error = getattr(self.pw_manager, "last_error", "")
                    if last_error:
                        self._show_toast(f"Playwright 시작 실패: {last_error}", "error")
                    # EXE 환경에서도 사용 가능하도록 Chromium 설치 UX 제공
                    choice = QMessageBox.question(
                        self,
                        "Playwright 시작 실패",
                        "Playwright Chromium이 설치되지 않았거나 실행에 실패했습니다.\n\n"
                        "Chromium을 지금 설치하시겠습니까? (playwright install chromium)",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    if choice == QMessageBox.StandardButton.Yes:
                        self._show_toast("Chromium 설치 중... (잠시 기다려주세요)", "info", 4000)
                        ok = PlaywrightManager.install_chromium()
                        if ok and self.pw_manager.launch(headless=False, stealth=True):
                            if url != "about:blank":
                                self.pw_manager.navigate(url)
                            self.lbl_pw_status.setText("● 연결됨")
                            self.lbl_pw_status.setStyleSheet("color: #a6e3a1;")
                            self.btn_pw_toggle.setText("Playwright 종료")
                            self._show_toast("Playwright 브라우저가 시작되었습니다.", "success")
                        else:
                            self._show_toast("Chromium 설치/시작 실패. 콘솔 로그를 확인하세요.", "error")
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
        self._show_toast(f"{scan_label} 스캔 중...", "info", 2000)
        
        try:
            with perf_span("ui.scan_page_elements"):
                elements = self.pw_manager.scan_elements(scan_type, max_count=50)
                
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
                    
                    btn_use = QPushButton("사용")
                    btn_use.setObjectName("success")
                    btn_use.setCursor(Qt.CursorShape.PointingHandCursor)
                    btn_use.clicked.connect(lambda checked, e=elem: self._use_scanned_element(e))
                    self.table_scan_results.setCellWidget(row, 3, btn_use)

                self.table_scan_results.setUpdatesEnabled(True)
                self.lbl_scan_summary.setText(f"스캔된 요소: {len(elements)}개")
                self._show_toast(f"{len(elements)}개의 {scan_label}를 찾았습니다.", "success")
            
        except Exception as e:
            self.table_scan_results.setUpdatesEnabled(True)
            self._show_toast(f"스캔 실패: {e}", "error")

    def _use_scanned_element(self, element):
        """스캔된 요소를 편집기로 로드"""
        self.input_xpath.setPlainText(element.xpath)
        self.input_css.setText(element.css_selector)
        
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
            self.pw_manager.highlight(element.xpath, 2000)

    def _reset_history_baseline(self):
        """현재 항목 목록을 Undo/Redo 기준 상태로 재설정."""
        self.history_manager.initialize(self.config.items)
        self._update_undo_redo_actions()

    def _update_undo_redo_actions(self):
        """Undo/Redo 액션 상태 업데이트"""
        if self.undo_action is None or self.redo_action is None:
            return
        self.undo_action.setEnabled(self.history_manager.can_undo())
        self.redo_action.setEnabled(self.history_manager.can_redo())
        
        if self.history_manager.can_undo():
            self.undo_action.setText(f"↩️ 실행 취소 ({self.history_manager.get_undo_description()})")
        else:
            self.undo_action.setText("↩️ 실행 취소")

    def _undo(self):
        """실행 취소"""
        restored = self.history_manager.undo()
        if restored is not None:
            self._restore_items_from_dicts(restored)
            self._filter_options_dirty = True
            self._refresh_table(refresh_filters=True)
            self._update_undo_redo_actions()
            self._show_toast("실행 취소됨", "info")

    def _redo(self):
        """다시 실행"""
        restored = self.history_manager.redo()
        if restored is not None:
            self._restore_items_from_dicts(restored)
            self._filter_options_dirty = True
            self._refresh_table(refresh_filters=True)
            self._update_undo_redo_actions()
            self._show_toast("다시 실행됨", "info")

    def _restore_items_from_dicts(self, item_dicts: list):
        """딕셔너리 리스트에서 XPathItem 복원"""
        restored_items = []
        for d in item_dicts:
            item = XPathItem(
                name=d.get('name', ''),
                xpath=d.get('xpath', ''),
                category=d.get('category', 'common'),
                description=d.get('description', ''),
                css_selector=d.get('css_selector', ''),
                is_verified=d.get('is_verified', False),
                element_tag=d.get('element_tag', ''),
                element_text=d.get('element_text', ''),
                found_window=d.get('found_window', ''),
                found_frame=d.get('found_frame', ''),
                is_favorite=d.get('is_favorite', False),
                tags=d.get('tags', []),
                test_count=d.get('test_count', 0),
                success_count=d.get('success_count', 0),
                last_tested=d.get('last_tested', ''),
                sort_order=d.get('sort_order', 0),
                alternatives=d.get('alternatives', []),
                element_attributes=d.get('element_attributes', {}),
                screenshot_path=d.get('screenshot_path', ''),
                ai_generated=d.get('ai_generated', False)
            )
            restored_items.append(item)
        self.config.replace_items(restored_items)
        self._table_data_dirty = True

    def _save_item_with_history(self):
        """항목 저장 (히스토리 기록 포함)"""
        name = self.input_name.text().strip()
        existing = self.config.get_item(name)
        action = "update" if existing else "add"
        
        # 변경 전 상태 저장
        self.history_manager.push_state(
            self.config.items, action, name,
            f"{name} 항목 {'수정' if existing else '추가'}"
        )
        
        # 원래 저장 로직은 _save_item()에서 처리
        self._update_undo_redo_actions()

    def _show_xpath_alternatives(self):
        """XPath 대안 제안 다이얼로그"""
        xpath = self.input_xpath.toPlainText().strip()
        
        if not xpath:
            self._show_toast("XPath를 먼저 입력하세요.", "warning")
            return
        
        if not self.browser.is_alive():
            self._show_toast("브라우저를 먼저 연결하세요.", "warning")
            return
        
        # 요소 정보 가져오기
        element_info = self.browser.get_element_info(xpath)
        
        if not element_info or not element_info.get('found'):
            self._show_toast("요소를 찾을 수 없습니다.", "error")
            return
        
        # 대안 생성
        element_info['original_xpath'] = xpath
        alternatives = self.optimizer.generate_alternatives(element_info)
        
        if not alternatives:
            self._show_toast("대안을 생성할 수 없습니다.", "warning")
            return
        
        # 다이얼로그 표시
        dialog = QDialog(self)
        dialog.setWindowTitle("💡 XPath 대안 제안")
        dialog.resize(700, 500)
        
        layout = QVBoxLayout(dialog)
        
        # 요소 정보 요약
        info_text = f"요소: <{element_info.get('tag', '?')}>"
        if element_info.get('id'):
            info_text += f" id='{element_info['id']}'"
        if element_info.get('class'):
            info_text += f" class='{element_info['class'][:30]}...'" if len(element_info.get('class', '')) > 30 else f" class='{element_info.get('class', '')}'"
        
        lbl_info = QLabel(info_text)
        lbl_info.setWordWrap(True)
        lbl_info.setStyleSheet("color: #89b4fa; padding: 5px;")
        layout.addWidget(lbl_info)
        
        # 대안 테이블
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["점수", "전략", "XPath", "사용"])
        alt_hh = table.horizontalHeader()
        if alt_hh is not None:
            alt_hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        table.setColumnWidth(0, 50)
        table.setColumnWidth(1, 100)
        table.setColumnWidth(3, 60)
        alt_vh = table.verticalHeader()
        if alt_vh is not None:
            alt_vh.setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        
        for alt in alternatives:
            row = table.rowCount()
            table.insertRow(row)
            
            # 점수
            score_item = QTableWidgetItem(f"{alt.robustness_score:.0f}")
            score_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if alt.robustness_score >= 80:
                score_item.setForeground(QColor("#a6e3a1"))
            elif alt.robustness_score >= 50:
                score_item.setForeground(QColor("#fab387"))
            else:
                score_item.setForeground(QColor("#f38ba8"))
            table.setItem(row, 0, score_item)
            
            # 전략
            table.setItem(row, 1, QTableWidgetItem(alt.strategy))
            
            # XPath
            xpath_item = QTableWidgetItem(alt.xpath)
            xpath_item.setToolTip(alt.description)
            table.setItem(row, 2, xpath_item)
            
            # 사용 버튼
            btn_use = QPushButton("사용")
            btn_use.setObjectName("success")
            btn_use.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_use.clicked.connect(lambda checked, x=alt.xpath: (
                self.input_xpath.setPlainText(x),
                self._show_toast("XPath 적용됨", "success"),
                dialog.accept()
            ))
            table.setCellWidget(row, 3, btn_use)
        
        layout.addWidget(table)
        
        # 닫기 버튼
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(dialog.reject)
        layout.addWidget(btn_close)
        
        dialog.exec()

    def _show_ai_assistant(self):
        """AI XPath 추천 다이얼로그"""
        dialog = QDialog(self)
        dialog.setWindowTitle("🤖 AI XPath 추천")
        dialog.resize(600, 450)
        
        layout = QVBoxLayout(dialog)
        
        # API 상태
        if self.ai_assistant.is_available():
            provider = (self.ai_assistant._provider or "openai").capitalize()
            status_text = f"✅ {provider} API 연결됨"
            status_color = "#a6e3a1"
        else:
            status_text = "⚠️ API 키 미설정 (규칙 기반 모드)"
            status_color = "#fab387"
        
        lbl_status = QLabel(status_text)
        lbl_status.setStyleSheet(f"color: {status_color}; font-weight: bold;")
        layout.addWidget(lbl_status)
        
        # 입력
        layout.addWidget(QLabel("찾고자 하는 요소를 설명하세요:"))
        self._ai_input = QPlainTextEdit()
        self._ai_input.setMaximumHeight(80)
        self._ai_input.setPlaceholderText("예: 로그인 버튼, 이메일 입력창, 예매하기 링크...")
        layout.addWidget(self._ai_input)
        
        # 생성 버튼
        btn_generate = QPushButton("🔮 XPath 생성")
        btn_generate.setObjectName("primary")
        btn_generate.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(btn_generate)
        
        # 결과 영역
        layout.addWidget(QLabel("추천 결과:"))
        self._ai_result_text = QPlainTextEdit()
        self._ai_result_text.setReadOnly(True)
        self._ai_result_text.setStyleSheet("font-family: 'Consolas', monospace; background-color: #181825;")
        layout.addWidget(self._ai_result_text)
        
        # 신뢰도 라벨
        self._ai_confidence_label = QLabel("")
        layout.addWidget(self._ai_confidence_label)

        def _apply_ai_result(result):
            self._ai_last_xpath = result.xpath or ""
            output = f"추천 XPath:\n{result.xpath}\n\n"
            if result.alternative_xpaths:
                output += "대안:\n" + "\n".join(f"  - {x}" for x in result.alternative_xpaths) + "\n\n"
            output += f"설명:\n{result.explanation}"
            self._ai_result_text.setPlainText(output)
            
            conf = result.confidence * 100
            if conf >= 70:
                self._ai_confidence_label.setText(f"신뢰도: {conf:.0f}% (높음)")
                self._ai_confidence_label.setStyleSheet("color: #a6e3a1;")
            elif conf >= 40:
                self._ai_confidence_label.setText(f"신뢰도: {conf:.0f}% (보통)")
                self._ai_confidence_label.setStyleSheet("color: #fab387;")
            else:
                self._ai_confidence_label.setText(f"신뢰도: {conf:.0f}% (낮음)")
                self._ai_confidence_label.setStyleSheet("color: #f38ba8;")

        def _on_ai_generated(request_id: int, result):
            if request_id != self._ai_request_id:
                return
            _apply_ai_result(result)

        def _on_ai_failed(request_id: int, error: str):
            if request_id != self._ai_request_id:
                return
            self._ai_last_xpath = ""
            self._ai_result_text.setPlainText(f"생성 실패:\n{error}")
            self._ai_confidence_label.setText("")

        def _on_ai_worker_finished(worker):
            if self.ai_worker is worker:
                self.ai_worker = None
            btn_generate.setEnabled(True)
        
        def generate():
            with perf_span("ui.ai_generate_click"):
                desc = self._ai_input.toPlainText().strip()
                if not desc:
                    self._show_toast("설명을 입력하세요.", "warning")
                    return

                self._ai_request_id += 1
                request_id = self._ai_request_id

                if self.ai_worker and self.ai_worker.isRunning():
                    self.ai_worker.cancel()

                btn_generate.setEnabled(False)
                self._ai_last_xpath = ""
                self._ai_result_text.setPlainText("생성 중...")
                self._ai_confidence_label.setText("")

                worker = AIGenerateWorker(self.ai_assistant, desc, request_id)
                worker.generated.connect(_on_ai_generated)
                worker.failed.connect(_on_ai_failed)
                worker.finished.connect(lambda w=worker: _on_ai_worker_finished(w))
                self.ai_worker = worker
                worker.start()
        
        btn_generate.clicked.connect(generate)
        
        # 적용 버튼
        btn_layout = QHBoxLayout()
        
        btn_apply = QPushButton("📋 편집기에 적용")
        btn_apply.clicked.connect(lambda: (
            self.input_xpath.setPlainText(self._ai_last_xpath or ""),
            self._show_toast("XPath 적용됨", "success") if self._ai_last_xpath else self._show_toast("적용할 XPath가 없습니다.", "warning")
        ))
        btn_layout.addWidget(btn_apply)
        
        btn_settings = QPushButton("⚙️ API 설정")
        btn_settings.clicked.connect(lambda: self._configure_ai_api(dialog))
        btn_layout.addWidget(btn_settings)
        
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(dialog.reject)
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)
        dialog.finished.connect(
            lambda _=None: (
                self.ai_worker.cancel() if self.ai_worker and self.ai_worker.isRunning() else None
            )
        )
        dialog.exec()

    def _configure_ai_api(self, parent_dialog):
        """AI API 설정 (Provider 지원)"""
        dialog = QDialog(parent_dialog)
        dialog.setWindowTitle("⚙️ AI 설정")
        dialog.resize(400, 300)
        
        layout = QVBoxLayout(dialog)
        
        # Provider 선택
        layout.addWidget(QLabel("AI 제공자:"))
        combo_provider = QComboBox()
        combo_provider.addItems(["openai", "gemini"])
        combo_provider.setCurrentText(self.ai_assistant._provider)
        layout.addWidget(combo_provider)
        
        # API 키 입력
        layout.addWidget(QLabel("API 키:"))
        input_key = QLineEdit()
        input_key.setEchoMode(QLineEdit.EchoMode.Password)
        if self.ai_assistant._provider == "openai":
            input_key.setText(self.ai_assistant._config.get('openai_api_key', ''))
        else:
            input_key.setText(self.ai_assistant._config.get('gemini_api_key', ''))
        layout.addWidget(input_key)
        
        # Model 입력
        layout.addWidget(QLabel("모델:"))
        input_model = QLineEdit()
        input_model.setText(self.ai_assistant._model)
        layout.addWidget(input_model)
        
        # 힌트
        lbl_hint = QLabel("OpenAI 권장: gpt-4o-mini, gpt-4o\nGemini 권장: gemini-flash-latest, gemini-pro")
        lbl_hint.setStyleSheet("color: #7f849c; font-size: 11px;")
        layout.addWidget(lbl_hint)
        
        # Provider 변경 시 처리
        def on_provider_change(text):
            input_key.clear()
            if text == "openai":
                input_key.setText(self.ai_assistant._config.get('openai_api_key', ''))
                input_model.setText("gpt-4o-mini")
            else:
                input_key.setText(self.ai_assistant._config.get('gemini_api_key', ''))
                input_model.setText("gemini-flash-latest")
                
        combo_provider.currentTextChanged.connect(on_provider_change)
        
        # 버튼 레이아웃
        btn_layout = QHBoxLayout()
        
        btn_save = QPushButton("저장")
        btn_save.setObjectName("success")
        def save():
            provider = combo_provider.currentText()
            key = input_key.text().strip()
            model = input_model.text().strip()
            
            if not key:
                self._show_toast("API 키를 입력하세요.", "warning")
                return
                
            self.ai_assistant.configure(key, model, provider)
            self._show_toast(f"{provider} 설정이 저장되었습니다.", "success")
            dialog.accept()
            
        btn_save.clicked.connect(save)
        btn_layout.addWidget(btn_save)
        
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(dialog.reject)
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)
        
        dialog.exec()

    def _show_diff_analyzer(self):
        """Diff 분석 다이얼로그"""
        if not self.browser.is_alive():
            self._show_toast("브라우저를 먼저 연결하세요.", "warning")
            return
        
        if not self.config.items:
            self._show_toast("분석할 항목이 없습니다.", "warning")
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("🔍 XPath 변경 감지 (Diff 분석)")
        dialog.resize(800, 550)
        
        layout = QVBoxLayout(dialog)
        
        # 분석 버튼
        btn_analyze = QPushButton("🔍 전체 분석 실행")
        btn_analyze.setObjectName("warning")
        btn_analyze.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(btn_analyze)
        
        # 요약 라벨
        lbl_summary = QLabel("분석 버튼을 클릭하여 시작하세요.")
        lbl_summary.setStyleSheet("font-size: 14px; padding: 10px;")
        layout.addWidget(lbl_summary)
        
        # 결과 테이블
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["상태", "항목", "변경 사항", "XPath"])
        diff_hh = table.horizontalHeader()
        if diff_hh is not None:
            diff_hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        table.setColumnWidth(0, 50)
        table.setColumnWidth(1, 120)
        table.setColumnWidth(3, 200)
        diff_vh = table.verticalHeader()
        if diff_vh is not None:
            diff_vh.setVisible(False)
        layout.addWidget(table)
        
        def _render_diff_results(results):
            table.setUpdatesEnabled(False)
            try:
                table.setRowCount(len(results))
                unchanged = modified = missing = 0
                for row, result in enumerate(results):
                    status_item = QTableWidgetItem(result.status_icon)
                    status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    table.setItem(row, 0, status_item)

                    table.setItem(row, 1, QTableWidgetItem(result.item_name))

                    changes_text = ", ".join(result.changes) if result.changes else "-"
                    table.setItem(row, 2, QTableWidgetItem(changes_text))

                    xpath_short = result.xpath[:40] + "..." if len(result.xpath) > 40 else result.xpath
                    xpath_item = QTableWidgetItem(xpath_short)
                    xpath_item.setToolTip(result.xpath)
                    table.setItem(row, 3, xpath_item)

                    if result.status == "unchanged":
                        unchanged += 1
                    elif result.status == "modified":
                        modified += 1
                    elif result.status == "missing":
                        missing += 1
                lbl_summary.setText(f"분석 완료: ✅ 변경없음 {unchanged}개 | ⚠️ 수정됨 {modified}개 | ❌ 찾지못함 {missing}개")
            finally:
                table.setUpdatesEnabled(True)

        def _on_diff_progress(_value, message):
            lbl_summary.setText(message)

        def _on_diff_completed(results):
            btn_analyze.setEnabled(True)
            self.diff_worker = None
            _render_diff_results(results)

        def _on_diff_failed(message):
            btn_analyze.setEnabled(True)
            self.diff_worker = None
            lbl_summary.setText(f"분석 실패: {message}")

        def run_analysis():
            if self.diff_worker and self.diff_worker.isRunning():
                return
            lbl_summary.setText("분석 중...")
            btn_analyze.setEnabled(False)
            self.diff_worker = DiffAnalyzeWorker(list(self.config.items), self.browser, self.diff_analyzer)
            self.diff_worker.progress.connect(_on_diff_progress)
            self.diff_worker.completed.connect(_on_diff_completed)
            self.diff_worker.failed.connect(_on_diff_failed)
            self.diff_worker.start()
        
        btn_analyze.clicked.connect(run_analysis)

        dialog.finished.connect(
            lambda _=None: (
                self.diff_worker.cancel() if self.diff_worker and self.diff_worker.isRunning() else None
            )
        )
        
        # 닫기 버튼
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(dialog.reject)
        layout.addWidget(btn_close)
        
        dialog.exec()

    def keyPressEvent(self, a0):
        """키보드 이벤트 처리 - ESC로 배치 테스트 취소"""
        from PyQt6.QtCore import Qt
        if a0.key() == Qt.Key.Key_Escape:
            if self.batch_worker and self.batch_worker.isRunning():
                self.batch_worker.cancel()
        super().keyPressEvent(a0)

    def _save_settings(self):
        """설정 저장 (추가 설정용 확장 포인트)"""
        # 현재는 geometry만 별도 저장, 필요시 확장
        pass

    def closeEvent(self, a0):
        """종료 처리"""
        logger.info("앱 종료 시작...")

        # 종료 중 상태 체크 타이머가 추가 로그를 만들지 않도록 선제 정지
        if hasattr(self, "check_timer") and self.check_timer is not None:
            self.check_timer.stop()
        
        # 설정 저장
        self.settings.setValue("geometry", self.saveGeometry())
        self._save_settings()  # 추가 설정 저장
        
        # 워커 스레드 정리
        if self.picker_watcher and self.picker_watcher.isRunning():
            logger.debug("PickerWatcher 종료 대기 중...")
            self.picker_watcher.stop()
            if not self.picker_watcher.wait(WORKER_WAIT_TIMEOUT):
                logger.warning("PickerWatcher 강제 종료")
            
        if self.validate_worker and self.validate_worker.isRunning():
            logger.debug("ValidateWorker 종료 대기 중...")
            self.validate_worker.cancel()
            if not self.validate_worker.wait(WORKER_WAIT_TIMEOUT):
                logger.warning("ValidateWorker 강제 종료")

        if self.live_preview_worker and self.live_preview_worker.isRunning():
            self.live_preview_worker.cancel()
            self.live_preview_worker.wait(WORKER_WAIT_TIMEOUT)

        if self.ai_worker and self.ai_worker.isRunning():
            self.ai_worker.cancel()
            self.ai_worker.wait(WORKER_WAIT_TIMEOUT)

        if self.diff_worker and self.diff_worker.isRunning():
            self.diff_worker.cancel()
            self.diff_worker.wait(WORKER_WAIT_TIMEOUT)

        if self.batch_worker and self.batch_worker.isRunning():
            self.batch_worker.cancel()
            self.batch_worker.wait(WORKER_WAIT_TIMEOUT)
        
        # v3.4: Playwright 종료
        if self.pw_manager:
            try:
                self.pw_manager.close()
            except Exception:
                pass  # Playwright 종료 실패 시 무시
            
        # 통계 저장
        if hasattr(self, 'stats_manager'):
            try:
                self.stats_manager.shutdown(timeout=5.0)
            except Exception:
                self.stats_manager.save()
        
        log_perf_summary()
             
        self.browser.close()
        logger.info("앱 종료 완료")
        a0.accept()
