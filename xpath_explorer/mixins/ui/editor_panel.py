# -*- coding: utf-8 -*-
# pyright: reportAttributeAccessIssue=false, reportCallIssue=false, reportArgumentType=false
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
    CATEGORY_LABELS,
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


class ExplorerUIEditorPanelMixin:
    def _create_editor_panel(self):
        """편집기 패널 - v3.4: 탭 구조 및 휠 스크롤 방지"""
        layout = QVBoxLayout(self.right_panel)
        layout.setContentsMargins(10, 0, 0, 0)
        
        # 탭 위젯 생성
        self.right_tabs = QTabWidget()
        self.right_tabs.setDocumentMode(True)
        
        # =====================================================================
        # 탭 1: 편집기
        # =====================================================================
        editor_tab = QWidget()
        editor_scroll = QScrollArea()
        editor_scroll.setWidgetResizable(True)
        editor_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        editor_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollArea > QWidget > QWidget {
                background: transparent;
            }
        """)
        
        editor_content = QWidget()
        editor_layout = QVBoxLayout(editor_content)
        editor_layout.setContentsMargins(5, 10, 5, 10)
        editor_layout.setSpacing(10)
        
        # 1. 요소 선택기 (크게 강조)
        group_picker = QGroupBox("요소 선택기")
        picker_layout = QVBoxLayout()
        
        btn_picker = QPushButton("🎯 요소 선택 시작")
        btn_picker.setObjectName("picker")
        btn_picker.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_picker.setToolTip("브라우저에서 요소를 직접 클릭하여 XPath를 추출합니다.")
        btn_picker.clicked.connect(self._start_picker)
        picker_layout.addWidget(btn_picker)
        
        # 오버레이 모드 체크박스
        self.chk_overlay = QCheckBox("오버레이 모드 (클릭 방지)")
        self.chk_overlay.setToolTip("체크 시 웹페이지의 버튼이 클릭되지 않고 선택만 됩니다.")
        picker_layout.addWidget(self.chk_overlay)

        picker_action_row = QHBoxLayout()
        self.btn_picker_lock = QPushButton("📌 현재 요소 고정")
        self.btn_picker_lock.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_picker_lock.setToolTip("브라우저에서 마우스를 올린 요소를 즉시 고정합니다.")
        self.btn_picker_lock.clicked.connect(self._force_lock_picker)
        self.btn_picker_lock.setEnabled(False)
        picker_action_row.addWidget(self.btn_picker_lock)

        self.btn_picker_unlock = QPushButton("🔓 고정 해제")
        self.btn_picker_unlock.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_picker_unlock.setToolTip("현재 고정된 요소를 해제하고 선택 모드로 돌아갑니다.")
        self.btn_picker_unlock.clicked.connect(self._force_unlock_picker)
        self.btn_picker_unlock.setEnabled(False)
        picker_action_row.addWidget(self.btn_picker_unlock)
        picker_layout.addLayout(picker_action_row)
        
        group_picker.setLayout(picker_layout)
        editor_layout.addWidget(group_picker)
        
        # 2. 상세 편집
        group_edit = QGroupBox("상세 편집")
        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        
        self.input_name = QLineEdit()
        self.input_name.setPlaceholderText("예: 로그인_버튼")
        form_layout.addRow(QLabel("이름:"), self.input_name)
        
        # 카테고리 (NoWheelComboBox 사용)
        self.input_category = NoWheelComboBox()
        self.input_category.setEditable(True)
        for value, label in CATEGORY_LABELS.items():
            self.input_category.addItem(label, value)
        form_layout.addRow(QLabel("카테고리:"), self.input_category)
        
        self.input_desc = QLineEdit()
        self.input_desc.setPlaceholderText("항목에 대한 설명")
        form_layout.addRow(QLabel("설명:"), self.input_desc)
        
        # v3.3: 태그 입력
        self.input_tags = QLineEdit()
        self.input_tags.setPlaceholderText("태그 (콤마 구분, 예: 중요, 로그인, 필수)")
        self.input_tags.setToolTip("여러 태그를 콤마(,)로 구분하여 입력하세요")
        form_layout.addRow(QLabel("태그:"), self.input_tags)
        
        group_edit.setLayout(form_layout)
        editor_layout.addWidget(group_edit)
        
        # 3. XPath & CSS
        group_code = QGroupBox("선택자")
        code_layout = QVBoxLayout()
        
        # XPath
        xpath_header = QHBoxLayout()
        xpath_header.addWidget(QLabel("XPath:"))
        
        # v4.0: 실시간 매칭 미리보기
        self.lbl_live_preview = QLabel("🔍 매칭: -")
        self.lbl_live_preview.setStyleSheet("color: #6c7086; font-size: 11px;")
        self.lbl_live_preview.setToolTip("입력 중인 XPath에 매칭되는 요소 수")
        xpath_header.addStretch()
        xpath_header.addWidget(self.lbl_live_preview)
        code_layout.addLayout(xpath_header)
        
        xpath_row = QHBoxLayout()
        self.input_xpath = QPlainTextEdit()
        self.input_xpath.setMaximumHeight(60)
        self.input_xpath.setPlaceholderText("//div[@id='example']")
        # v4.0: 실시간 미리보기 연결
        self.input_xpath.textChanged.connect(self._on_xpath_text_changed)
        xpath_row.addWidget(self.input_xpath)
        
        # XPath 버튼 그룹
        xpath_btn_layout = QVBoxLayout()
        xpath_btn_layout.setSpacing(4)
        
        btn_copy_xpath = QPushButton("📋")
        btn_copy_xpath.setObjectName("icon_btn")
        btn_copy_xpath.setToolTip("XPath 복사")
        btn_copy_xpath.clicked.connect(self._copy_xpath)
        xpath_btn_layout.addWidget(btn_copy_xpath)
        
        # v4.0: XPath 대안 제안 버튼
        self.btn_alternatives = QPushButton("💡")
        self.btn_alternatives.setObjectName("icon_btn")
        self.btn_alternatives.setToolTip("XPath 대안 제안")
        self.btn_alternatives.clicked.connect(self._show_xpath_alternatives)
        xpath_btn_layout.addWidget(self.btn_alternatives)
        
        xpath_row.addLayout(xpath_btn_layout)
        code_layout.addLayout(xpath_row)
        
        # CSS
        code_layout.addWidget(QLabel("CSS 선택자:"))
        css_row = QHBoxLayout()
        self.input_css = QLineEdit()
        self.input_css.setPlaceholderText("#example .cls")
        css_row.addWidget(self.input_css)
        
        # CSS 복사 버튼
        btn_copy_css = QPushButton("📋")
        btn_copy_css.setObjectName("icon_btn")
        btn_copy_css.setToolTip("CSS 선택자 복사")
        btn_copy_css.clicked.connect(self._copy_css)
        css_row.addWidget(btn_copy_css)
        
        code_layout.addLayout(css_row)
        
        # 테스트 & 저장 버튼
        btn_row = QHBoxLayout()
        
        self.btn_test = QPushButton("검증")
        self.btn_test.setObjectName("warning")
        self.btn_test.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_test.setToolTip("현재 입력된 XPath가 브라우저에서 올바르게 동작하는지 확인합니다. (Ctrl+T)")
        self.btn_test.clicked.connect(self._test_xpath)
        btn_row.addWidget(self.btn_test)
        
        self.btn_highlight = QPushButton("하이라이트")
        self.btn_highlight.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_highlight.clicked.connect(self._highlight_xpath)
        btn_row.addWidget(self.btn_highlight)
        
        self.btn_save = QPushButton("목록에 저장")
        self.btn_save.setObjectName("success")
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.clicked.connect(self._save_item)
        btn_row.addWidget(self.btn_save)
        
        code_layout.addLayout(btn_row)
        group_code.setLayout(code_layout)
        editor_layout.addWidget(group_code)
        
        # 4. 검증 결과
        group_result = QGroupBox("검증 결과")
        result_layout = QVBoxLayout()
        
        self.txt_result = QTextEdit()
        self.txt_result.setReadOnly(True)
        self.txt_result.setMaximumHeight(100)
        self.txt_result.setStyleSheet("background-color: #181825; color: #a6e3a1; font-family: 'Consolas', monospace; border: 1px solid #45475a;")
        result_layout.addWidget(self.txt_result)
        
        group_result.setLayout(result_layout)
        editor_layout.addWidget(group_result)
        
        editor_layout.addStretch()
        
        editor_scroll.setWidget(editor_content)
        editor_tab_layout = QVBoxLayout(editor_tab)
        editor_tab_layout.setContentsMargins(0, 0, 0, 0)
        editor_tab_layout.addWidget(editor_scroll)
        
        self.right_tabs.addTab(editor_tab, "📝 편집기")
        
        # =====================================================================
        # 탭 2: 자동 탐색 (Playwright) - v3.5: 스크롤 추가
        # =====================================================================
        scan_tab = QWidget()
        scan_scroll = QScrollArea()
        scan_scroll.setWidgetResizable(True)
        scan_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scan_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollArea > QWidget > QWidget {
                background: transparent;
            }
        """)
        
        scan_content = QWidget()
        scan_inner_layout = QVBoxLayout(scan_content)
        scan_inner_layout.setContentsMargins(10, 10, 10, 10)
        scan_inner_layout.setSpacing(15)
        
        # Playwright 상태 및 컨트롤
        pw_status_group = QGroupBox("🎭 Playwright 브라우저")
        pw_status_layout = QHBoxLayout()
        pw_status_layout.setContentsMargins(12, 10, 12, 10)
        
        self.lbl_pw_status = QLabel("● 미연결")
        self.lbl_pw_status.setStyleSheet("color: #f38ba8; font-weight: bold;")
        pw_status_layout.addWidget(self.lbl_pw_status)
        pw_status_layout.addStretch()
        
        self.btn_pw_toggle = QPushButton("▶ Playwright 시작")
        self.btn_pw_toggle.setObjectName("primary")
        self.btn_pw_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pw_toggle.clicked.connect(self._toggle_playwright)
        pw_status_layout.addWidget(self.btn_pw_toggle)
        
        pw_status_group.setLayout(pw_status_layout)
        scan_inner_layout.addWidget(pw_status_group)
        
        # 스캔 설정
        scan_settings_group = QGroupBox("⚙️ 스캔 설정")
        scan_settings_layout = QVBoxLayout()
        scan_settings_layout.setContentsMargins(12, 10, 12, 10)
        scan_settings_layout.setSpacing(12)
        
        # 스캔 타입 선택
        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("스캔 타입:"))
        self.combo_scan_type = NoWheelComboBox()
        self.combo_scan_type.addItem("상호작용 요소", "interactive")
        self.combo_scan_type.addItem("버튼", "button")
        self.combo_scan_type.addItem("입력 필드", "input")
        self.combo_scan_type.addItem("링크", "link")
        self.combo_scan_type.addItem("폼", "form")
        self.combo_scan_type.setToolTip("버튼, 링크, 입력 필드 등 상호작용 가능한 요소를 선택해 스캔합니다.")
        type_row.addWidget(self.combo_scan_type, 1)
        scan_settings_layout.addLayout(type_row)
        
        # 스캔 버튼
        self.btn_scan = QPushButton("🔍 페이지 스캔")
        self.btn_scan.setObjectName("warning")
        self.btn_scan.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_scan.setMinimumHeight(40)
        self.btn_scan.clicked.connect(self._scan_page_elements)
        scan_settings_layout.addWidget(self.btn_scan)

        self.btn_scan_export_dom = QToolButton()
        self.btn_scan_export_dom.setText("🧾 DOM 추출 (.htm)")
        self.btn_scan_export_dom.setObjectName("primary")
        self.btn_scan_export_dom.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_scan_export_dom.setToolTip("DOM 저장 범위 선택")
        self.btn_scan_export_dom.setMinimumHeight(36)
        self.btn_scan_export_dom.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        playwright_dom_menu = QMenu(self.btn_scan_export_dom)
        playwright_dom_menu.addAction("전체 DOM 저장", lambda: self._export_dom_playwright_htm(scope="all", include_frames=True))
        playwright_dom_menu.addAction("현재 창 DOM 저장", lambda: self._export_dom_playwright_htm(scope="current", include_frames=False))
        playwright_dom_menu.addAction("현재 창 + iframe DOM 저장", lambda: self._export_dom_playwright_htm(scope="current", include_frames=True))
        self.btn_scan_export_dom.setMenu(playwright_dom_menu)
        scan_settings_layout.addWidget(self.btn_scan_export_dom)
        
        scan_settings_group.setLayout(scan_settings_layout)
        scan_inner_layout.addWidget(scan_settings_group)
        
        # 스캔 결과 테이블
        results_group = QGroupBox("📋 스캔 결과")
        results_layout = QVBoxLayout()
        results_layout.setContentsMargins(12, 10, 12, 10)
        
        self.table_scan_results = QTableWidget()
        self.table_scan_results.setColumnCount(4)
        self.table_scan_results.setHorizontalHeaderLabels(["XPath", "태그", "텍스트", "사용"])
        scan_hh = self.table_scan_results.horizontalHeader()
        if scan_hh is not None:
            scan_hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table_scan_results.setColumnWidth(1, 60)
        self.table_scan_results.setColumnWidth(2, 120)
        self.table_scan_results.setColumnWidth(3, 60)
        scan_vh = self.table_scan_results.verticalHeader()
        if scan_vh is not None:
            scan_vh.setVisible(False)
        self.table_scan_results.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_scan_results.setAlternatingRowColors(True)
        self.table_scan_results.setMinimumHeight(200)
        results_layout.addWidget(self.table_scan_results)
        
        # 스캔 결과 요약
        self.lbl_scan_summary = QLabel("스캔된 요소: 0개")
        self.lbl_scan_summary.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.lbl_scan_summary.setStyleSheet("color: #6c7086; font-size: 11px;")
        results_layout.addWidget(self.lbl_scan_summary)
        
        results_group.setLayout(results_layout)
        scan_inner_layout.addWidget(results_group)
        
        scan_inner_layout.addStretch()
        
        scan_scroll.setWidget(scan_content)
        scan_tab_layout = QVBoxLayout(scan_tab)
        scan_tab_layout.setContentsMargins(0, 0, 0, 0)
        scan_tab_layout.addWidget(scan_scroll)
        
        self.right_tabs.addTab(scan_tab, "🔍 자동 탐색")
        
        layout.addWidget(self.right_tabs)
