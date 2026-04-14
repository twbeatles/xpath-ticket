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


class ExplorerGenerationToolsMixin:
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

    def _show_xpath_template_library(self):
        """XPath 템플릿 라이브러리 다이얼로그."""
        dialog = QDialog(self)
        dialog.setWindowTitle("📚 XPath 템플릿 라이브러리")
        dialog.resize(920, 620)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("카테고리:"))
        combo_category = QComboBox()
        combo_category.addItem("전체", "")
        for category in sorted({t.category for t in self.code_generator.list_xpath_templates()}):
            combo_category.addItem(category_to_label(category), category)
        filter_row.addWidget(combo_category)

        filter_row.addWidget(QLabel("검색:"))
        input_keyword = QLineEdit()
        input_keyword.setPlaceholderText("템플릿명, XPath, 설명 검색")
        filter_row.addWidget(input_keyword, 1)
        layout.addLayout(filter_row)

        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["카테고리", "템플릿명", "XPath", "설명", "사용"])
        table_hh = table.horizontalHeader()
        if table_hh is not None:
            table_hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            table_hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            table_hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
            table_hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
            table_hh.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        table_vh = table.verticalHeader()
        if table_vh is not None:
            table_vh.setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        layout.addWidget(table, 1)

        lbl_summary = QLabel("")
        lbl_summary.setStyleSheet("color: #6c7086;")
        layout.addWidget(lbl_summary)

        current_rows: List[XPathTemplate] = []

        def apply_template(template: XPathTemplate):
            self.input_xpath.setPlainText(template.xpath)
            if not self.input_desc.text().strip():
                self.input_desc.setText(template.description)
            if not self.input_name.text().strip():
                self.input_name.setText(template.name.replace(" ", "_"))
            if hasattr(self, "right_tabs") and self.right_tabs is not None:
                self.right_tabs.setCurrentIndex(0)
            self._show_toast(f"템플릿 적용: {template.name}", "success")
            dialog.accept()

        def refresh_table():
            nonlocal current_rows
            keyword = input_keyword.text().strip()
            category = str(combo_category.currentData() or "")
            current_rows = self.code_generator.list_xpath_templates(
                category=category,
                keyword=keyword,
            )

            table.setRowCount(len(current_rows))
            for row, template in enumerate(current_rows):
                table.setItem(row, 0, QTableWidgetItem(category_to_label(template.category)))
                table.setItem(row, 1, QTableWidgetItem(template.name))

                xpath_item = QTableWidgetItem(template.xpath)
                xpath_item.setToolTip(template.xpath)
                table.setItem(row, 2, xpath_item)
                table.setItem(row, 3, QTableWidgetItem(template.description))

                btn_apply = QPushButton("적용")
                btn_apply.setObjectName("success")
                btn_apply.setCursor(Qt.CursorShape.PointingHandCursor)
                btn_apply.clicked.connect(lambda _checked=False, t=template: apply_template(t))
                table.setCellWidget(row, 4, btn_apply)

            lbl_summary.setText(f"템플릿 {len(current_rows)}개")

        def on_double_click(row: int, _column: int):
            if 0 <= row < len(current_rows):
                apply_template(current_rows[row])

        table.cellDoubleClicked.connect(on_double_click)
        combo_category.currentIndexChanged.connect(lambda _=None: refresh_table())
        input_keyword.textChanged.connect(lambda _=None: refresh_table())
        refresh_table()

        btn_row = QHBoxLayout()
        btn_copy = QPushButton("📋 선택 XPath 복사")
        btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_row.addWidget(btn_copy)

        def copy_selected():
            row = table.currentRow()
            if row < 0 or row >= len(current_rows):
                self._show_toast("복사할 템플릿을 선택하세요.", "warning")
                return
            clipboard = QApplication.clipboard()
            if clipboard is not None:
                clipboard.setText(current_rows[row].xpath)
            self._show_toast("XPath가 클립보드에 복사되었습니다.", "success")

        btn_copy.clicked.connect(copy_selected)

        btn_row.addStretch()
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(dialog.reject)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

        dialog.exec()

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
