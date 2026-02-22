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


class ExplorerUIMixin:
    def _init_ui(self):
        """UI 초기화"""
        self.setWindowTitle(APP_TITLE)
        self.resize(1400, 900)
        
        # 중앙 위젯
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 메인 레이아웃
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # 1. 메뉴바
        self._create_menu()
        
        # 2. 브라우저 컨트롤 패널
        self._create_browser_panel()
        main_layout.addLayout(self.browser_layout)
        
        # 2.5 URL 패널 (Collapsible)
        self.url_panel = self._create_url_panel()
        main_layout.addWidget(self.url_panel)

        
        # 3. 메인 작업 영역 (스플리터)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self.splitter, 1)
        
        # 3.1 왼쪽: XPath 목록
        self.left_panel = QWidget()
        self._create_list_panel()
        self.splitter.addWidget(self.left_panel)
        
        # 3.2 오른쪽: 상세 편집 및 도구
        self.right_panel = QWidget()
        self._create_editor_panel()
        self.splitter.addWidget(self.right_panel)
        
        # 스플리터 비율 (6:4)
        self.splitter.setStretchFactor(0, 6)
        self.splitter.setStretchFactor(1, 4)
        
        # 4. 상태 표시줄 패널
        self._create_status_panel()
        main_layout.addLayout(self.status_layout)
        
        # 스타일 적용
        self.setStyleSheet(STYLE)
        
        # Toast 알림 초기화
        self.toast = ToastWidget(self)

    def resizeEvent(self, a0):
        """[BUG-002] 윈도우 리사이즈 시 Toast 위치 업데이트"""
        super().resizeEvent(a0)
        if hasattr(self, 'toast') and self.toast.isVisible():
            self.toast._update_position()

    def _create_menu(self):
        """메뉴바"""
        menubar = cast(QMenuBar, self.menuBar())
        if menubar is None:
            return
        
        # 파일 메뉴
        file_menu = cast(QMenu, menubar.addMenu('파일(&F)'))
        
        new_action = QAction('새 설정(&N)', self)
        new_action.setShortcut('Ctrl+N')
        new_action.triggered.connect(self._new_config)
        file_menu.addAction(new_action)
        
        open_action = QAction('설정 열기(&O)...', self)
        open_action.setShortcut('Ctrl+O')
        open_action.triggered.connect(self._open_config)
        file_menu.addAction(open_action)
        
        save_action = QAction('설정 저장(&S)', self)
        save_action.setShortcut('Ctrl+S')
        save_action.triggered.connect(self._save_config)
        file_menu.addAction(save_action)
        
        file_menu.addSeparator()
        
        export_menu = cast(QMenu, file_menu.addMenu('내보내기(&E)'))
        formats = [
             ('JSON (*.json)', 'json'),
             ('CSV (*.csv)', 'csv'),
             ('Python Selenium (*.py)', 'python'),
             ('JavaScript (*.js)', 'javascript')
        ]
        for name, fmt in formats:
            action = QAction(name, self)
            action.triggered.connect(lambda checked, f=fmt: self._export(f))
            export_menu.addAction(action)
            
        file_menu.addSeparator()
        exit_action = QAction('종료(&X)', self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # v4.0 편집 메뉴 (Undo/Redo)
        edit_menu = cast(QMenu, menubar.addMenu('편집(&E)'))
        
        self.undo_action = QAction('↩️ 실행 취소', self)
        self.undo_action.setShortcut('Ctrl+Z')
        self.undo_action.triggered.connect(self._undo)
        self.undo_action.setEnabled(False)
        edit_menu.addAction(self.undo_action)
        
        self.redo_action = QAction('↪️ 다시 실행', self)
        self.redo_action.setShortcut('Ctrl+Y')
        self.redo_action.triggered.connect(self._redo)
        self.redo_action.setEnabled(False)
        edit_menu.addAction(self.redo_action)
        
        # 도구 메뉴
        tools_menu = cast(QMenu, menubar.addMenu('도구(&T)'))
        
        history_action = QAction('XPath 히스토리(&H)', self)
        history_action.setShortcut('Ctrl+H') # [UX-002] 단축키
        history_action.triggered.connect(self._show_xpath_history)
        tools_menu.addAction(history_action)
        
        validate_action = QAction('전체 유효성 검사(&V)', self)
        validate_action.setShortcut('F5')
        validate_action.triggered.connect(self._validate_all)
        tools_menu.addAction(validate_action)
        
        test_action = QAction('현재 XPath 테스트(&T)', self)
        test_action.setShortcut('Ctrl+T') # [UX-002] 단축키
        test_action.triggered.connect(self._test_xpath)
        tools_menu.addAction(test_action)
        
        cookies_menu = cast(QMenu, tools_menu.addMenu('쿠키 관리'))
        save_cookies_act = QAction('현재 쿠키 저장', self)
        save_cookies_act.triggered.connect(self._save_cookies)
        cookies_menu.addAction(save_cookies_act)
        load_cookies_act = QAction('쿠키 불러오기', self)
        load_cookies_act.triggered.connect(self._load_cookies)
        cookies_menu.addAction(load_cookies_act)
        clear_cookies_act = QAction('쿠키 삭제', self)
        clear_cookies_act.triggered.connect(self._clear_cookies)
        cookies_menu.addAction(clear_cookies_act)
        
        tools_menu.addSeparator()
        
        # v3.3 배치 테스트
        batch_menu = cast(QMenu, tools_menu.addMenu('📊 배치 테스트'))
        batch_all_action = QAction('전체 카테고리 테스트', self)
        batch_all_action.triggered.connect(lambda: self._batch_test())
        batch_menu.addAction(batch_all_action)
        
        batch_cat_action = QAction('카테고리 선택 테스트...', self)
        batch_cat_action.triggered.connect(self._batch_test_dialog)
        batch_menu.addAction(batch_cat_action)
        
        # v3.3 매크로 생성
        macro_action = QAction('🔧 매크로 생성...', self)
        macro_action.triggered.connect(self._show_macro_generator)
        tools_menu.addAction(macro_action)
        
        # v3.3 네트워크 분석
        network_action = QAction('🌐 네트워크 분석...', self)
        network_action.triggered.connect(self._show_network_analyzer)
        tools_menu.addAction(network_action)
        
        tools_menu.addSeparator()
        
        # v4.0 신규 도구
        ai_action = QAction('🤖 AI XPath 추천...', self)
        ai_action.triggered.connect(self._show_ai_assistant)
        tools_menu.addAction(ai_action)
        
        diff_action = QAction('🔍 Diff 분석 (변경 감지)...', self)
        diff_action.triggered.connect(self._show_diff_analyzer)
        tools_menu.addAction(diff_action)
        
        screenshot_action = QAction('📸 요소 스크린샷...', self)
        screenshot_action.triggered.connect(self._screenshot_current_element)
        tools_menu.addAction(screenshot_action)
        
        tools_menu.addSeparator()
        
        # v3.3 통계
        stats_action = QAction('📈 통계 보기', self)
        stats_action.triggered.connect(self._show_statistics)
        tools_menu.addAction(stats_action)
        
        # 보기 메뉴
        view_menu = cast(QMenu, menubar.addMenu('보기(&V)'))
        
        inc_font = QAction('폰트 크기 증가', self)
        inc_font.setShortcut('Ctrl++')
        inc_font.triggered.connect(self._increase_font)
        view_menu.addAction(inc_font)
        
        dec_font = QAction('폰트 크기 감소', self)
        dec_font.setShortcut('Ctrl+-')
        dec_font.triggered.connect(self._decrease_font)
        view_menu.addAction(dec_font)
        
        reset_font = QAction('폰트 크기 초기화', self)
        reset_font.setShortcut('Ctrl+0')
        reset_font.triggered.connect(self._reset_font)
        view_menu.addAction(reset_font)
        
        # 도움말 메뉴
        help_menu = cast(QMenu, menubar.addMenu('도움말(&H)'))
        
        shortcuts_action = QAction('단축키 목록(&K)', self)
        shortcuts_action.triggered.connect(self._show_shortcuts)
        help_menu.addAction(shortcuts_action)
        
        about_action = QAction('정보(&A)', self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _create_browser_panel(self):
        """브라우저 컨트롤 패널 - v3.6: 개선된 레이아웃"""
        self.browser_layout = QHBoxLayout()
        self.browser_layout.setSpacing(10)
        
        # 애니메이션 상태 인디케이터
        self.status_indicator = AnimatedStatusIndicator()
        self.browser_layout.addWidget(self.status_indicator)
        
        # 브라우저 열기/닫기 버튼
        self.btn_open = QPushButton("🌐 브라우저 열기")
        self.btn_open.setObjectName("primary")
        self.btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open.setToolTip("크롬 브라우저를 실행합니다.")
        self.btn_open.setMinimumWidth(120)
        self.browser_layout.addWidget(self.btn_open)
        self.btn_open.clicked.connect(self._toggle_browser)
        
        # 상태 텍스트 라벨
        self.lbl_status = QLabel("연결 안됨")
        self.lbl_status.setObjectName("status_disconnected")
        self.lbl_status.setToolTip("브라우저 연결 상태")
        self.browser_layout.addWidget(self.lbl_status)
        
        # 구분선
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.VLine)
        sep1.setStyleSheet("color: rgba(69, 71, 90, 0.5); max-width: 1px;")
        self.browser_layout.addWidget(sep1)
        
        # 사이트 프리셋
        self.combo_preset = NoWheelComboBox()
        self.combo_preset.addItems(SITE_PRESETS.keys())
        self.combo_preset.setMinimumWidth(90)
        self.combo_preset.setToolTip("사이트 프리셋 선택")
        self.combo_preset.currentTextChanged.connect(self._on_preset_changed)
        self.browser_layout.addWidget(self.combo_preset)
        
        # 구분선
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setStyleSheet("color: #45475a;")
        self.browser_layout.addWidget(sep2)
        
        # 창/프레임 (컴팩트)
        lbl_win = QLabel("창")
        lbl_win.setToolTip("브라우저 창/탭 선택")
        self.browser_layout.addWidget(lbl_win)
        self.combo_windows = NoWheelComboBox()
        self.combo_windows.setMinimumWidth(70)
        self.combo_windows.currentIndexChanged.connect(self._on_window_changed)
        self.browser_layout.addWidget(self.combo_windows)
        
        self.btn_refresh_wins = QPushButton("↻")
        self.btn_refresh_wins.setObjectName("icon_btn")
        self.btn_refresh_wins.setToolTip("창 목록 새로고침")
        self.btn_refresh_wins.setFixedSize(26, 26)
        self.btn_refresh_wins.clicked.connect(self._refresh_windows)
        self.browser_layout.addWidget(self.btn_refresh_wins)
        
        lbl_frame = QLabel("프레임")
        lbl_frame.setToolTip("iframe 선택")
        self.browser_layout.addWidget(lbl_frame)
        self.combo_frames = NoWheelComboBox()
        self.combo_frames.setMinimumWidth(70)
        self.browser_layout.addWidget(self.combo_frames)
        
        self.btn_scan_frames = QPushButton("🔍")
        self.btn_scan_frames.setObjectName("icon_btn")
        self.btn_scan_frames.setToolTip("iframe 스캔")
        self.btn_scan_frames.setFixedSize(26, 26)
        self.btn_scan_frames.clicked.connect(self._scan_frames)
        self.browser_layout.addWidget(self.btn_scan_frames)
        
        # 구분선
        sep3 = QFrame()
        sep3.setFrameShape(QFrame.Shape.VLine)
        sep3.setStyleSheet("color: #45475a;")
        self.browser_layout.addWidget(sep3)
        
        # URL 네비게이션 (컴팩트)
        self.btn_back = QPushButton("◀")
        self.btn_back.setObjectName("icon_btn")
        self.btn_back.setToolTip("뒤로가기")
        self.btn_back.setFixedSize(26, 26)
        self.btn_back.clicked.connect(self._browser_back)
        self.browser_layout.addWidget(self.btn_back)
        
        self.btn_forward = QPushButton("▶")
        self.btn_forward.setObjectName("icon_btn")
        self.btn_forward.setToolTip("앞으로가기")
        self.btn_forward.setFixedSize(26, 26)
        self.btn_forward.clicked.connect(self._browser_forward)
        self.browser_layout.addWidget(self.btn_forward)
        
        self.btn_refresh_page = QPushButton("↻")
        self.btn_refresh_page.setObjectName("icon_btn")
        self.btn_refresh_page.setToolTip("페이지 새로고침")
        self.btn_refresh_page.setFixedSize(26, 26)
        self.btn_refresh_page.clicked.connect(self._browser_refresh)
        self.browser_layout.addWidget(self.btn_refresh_page)
        
        # URL 입력창 (구버전 제거, 하단 Collapsible 영역으로 이동)
        self.browser_layout.addStretch()

    def _create_url_panel(self):
        """URL 입력 패널 (Collapsible)"""
        # 컨텐츠 위젯
        content = QWidget()
        layout = QHBoxLayout(content)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # 큰 URL 입력창
        self.input_url = QLineEdit()
        self.input_url.setObjectName("url_input_large")
        self.input_url.setPlaceholderText("https://...")
        self.input_url.returnPressed.connect(self._navigate)
        layout.addWidget(self.input_url, 1)
        
        # 큰 이동 버튼
        self.btn_go = QPushButton("이동")
        self.btn_go.setObjectName("primary")
        self.btn_go.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_go.setFixedSize(80, 42)
        self.btn_go.setStyleSheet("font-size: 15px; font-weight: bold;")
        self.btn_go.clicked.connect(self._navigate)
        layout.addWidget(self.btn_go)
        
        # 접이식 박스 생성
        self.url_collapsible = CollapsibleBox("🌐 URL 주소창", expanded=True)
        self.url_collapsible.setContentLayout(layout)
        
        return self.url_collapsible

    def _create_list_panel(self):
        """XPath 목록 패널 - v3.5: 스크롤 추가"""
        layout = QVBoxLayout(self.left_panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 스크롤 영역 생성
        list_scroll = QScrollArea()
        list_scroll.setWidgetResizable(True)
        list_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        list_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollArea > QWidget > QWidget {
                background: transparent;
            }
        """)
        
        list_content = QWidget()
        list_layout = QVBoxLayout(list_content)
        list_layout.setContentsMargins(0, 0, 10, 0)
        list_layout.setSpacing(10)
        
        # 헤더
        header_layout = QHBoxLayout()
        title = QLabel("📋 XPath 목록")
        title.setObjectName("title")
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        btn_add = QPushButton("+ 새 항목")
        btn_add.setObjectName("primary")
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.setToolTip("새로운 빈 항목 추가 (Ctrl+N)")
        btn_add.clicked.connect(self._add_new_item)
        header_layout.addWidget(btn_add)
        list_layout.addLayout(header_layout)
        
        # 검색창 (독립적으로 배치, 더 크게)
        search_group = QGroupBox("🔍 검색")
        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(10, 8, 10, 8)
        
        self.input_search = QLineEdit()
        self.input_search.setObjectName("search_input")
        self.input_search.setPlaceholderText("이름, 설명, XPath 검색...")
        self.input_search.setMinimumHeight(32)
        self.input_search.textChanged.connect(self._on_search_text_changed)
        search_layout.addWidget(self.input_search)
        
        # 검색 초기화 버튼
        self.btn_clear_search = QPushButton("✕")
        self.btn_clear_search.setObjectName("icon_btn")
        self.btn_clear_search.setFixedSize(28, 28)
        self.btn_clear_search.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear_search.setToolTip("검색어 초기화")
        self.btn_clear_search.clicked.connect(lambda: self.input_search.clear())
        self.btn_clear_search.setVisible(False)  # 기본 숨김
        search_layout.addWidget(self.btn_clear_search)
        
        search_group.setLayout(search_layout)
        list_layout.addWidget(search_group)
        
        # 필터 영역 (컴팩트하게)
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(8)
        
        filter_layout.addWidget(QLabel("카테고리:"))
        self.combo_filter = NoWheelComboBox()
        self.combo_filter.addItem("전체")
        self.combo_filter.setMinimumWidth(90)
        self.combo_filter.currentTextChanged.connect(lambda t: self._refresh_table(t))
        filter_layout.addWidget(self.combo_filter)
        
        filter_layout.addWidget(QLabel("태그:"))
        self.combo_tag_filter = NoWheelComboBox()
        self.combo_tag_filter.addItem("모든 태그")
        self.combo_tag_filter.currentTextChanged.connect(self._on_tag_filter_changed)
        self.combo_tag_filter.setMinimumWidth(90)
        filter_layout.addWidget(self.combo_tag_filter)
        
        self.chk_favorites_only = QCheckBox("⭐ 즐겨찾기")
        self.chk_favorites_only.stateChanged.connect(self._on_favorites_filter_changed)
        filter_layout.addWidget(self.chk_favorites_only)
        
        filter_layout.addStretch()
        
        list_layout.addLayout(filter_layout)
        
        # 목록 테이블 (Model/View 기반)
        self.table = QTableView()
        self.table.setModel(self.table_proxy)
        table_hh = self.table.horizontalHeader()
        if table_hh is not None:
            table_hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
            table_hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        table_vh = self.table.verticalHeader()
        if table_vh is not None:
            table_vh.setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(False)

        self.table.setColumnWidth(0, 30)   # 즐겨찾기
        self.table.setColumnWidth(1, 30)   # 상태 아이콘
        self.table.setColumnWidth(2, 140)  # 이름
        self.table.setColumnWidth(3, 90)   # 카테고리
        self.table.setColumnWidth(5, 60)   # 성공률
        self.table.setColumnWidth(6, 40)   # 삭제

        self.table.clicked.connect(self._on_table_clicked)
        table_sm = self.table.selectionModel()
        if table_sm is not None:
            table_sm.currentRowChanged.connect(self._on_item_selected)

        # 컨텍스트 메뉴
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        
        list_layout.addWidget(self.table, 1)
        
        # 요약 정보
        self.lbl_summary = QLabel("총 0개")
        self.lbl_summary.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.lbl_summary.setObjectName("info_label")
        list_layout.addWidget(self.lbl_summary)
        
        list_scroll.setWidget(list_content)
        layout.addWidget(list_scroll)

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
        
        group_picker.setLayout(picker_layout)
        editor_layout.addWidget(group_picker)
        
        # 2. 상세 편집
        group_edit = QGroupBox("상세 편집")
        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        
        self.input_name = QLineEdit()
        self.input_name.setPlaceholderText("예: login_btn")
        form_layout.addRow(QLabel("이름:"), self.input_name)
        
        # 카테고리 (NoWheelComboBox 사용)
        self.input_category = NoWheelComboBox()
        self.input_category.setEditable(True)
        self.input_category.addItems(["login", "booking", "seat", "captcha", "popup", "common"])
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
        group_code = QGroupBox("선택자 (Selectors)")
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
        code_layout.addWidget(QLabel("CSS Selector:"))
        css_row = QHBoxLayout()
        self.input_css = QLineEdit()
        self.input_css.setPlaceholderText("#example .cls")
        css_row.addWidget(self.input_css)
        
        # CSS 복사 버튼
        btn_copy_css = QPushButton("📋")
        btn_copy_css.setObjectName("icon_btn")
        btn_copy_css.setToolTip("CSS Selector 복사")
        btn_copy_css.clicked.connect(self._copy_css)
        css_row.addWidget(btn_copy_css)
        
        code_layout.addLayout(css_row)
        
        # 테스트 & 저장 버튼
        btn_row = QHBoxLayout()
        
        self.btn_test = QPushButton("검증 (Test)")
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
        self.combo_scan_type.addItems(["interactive", "button", "input", "link", "form"])
        self.combo_scan_type.setToolTip("interactive: 버튼, 링크, 입력 필드 등 상호작용 가능한 요소")
        type_row.addWidget(self.combo_scan_type, 1)
        scan_settings_layout.addLayout(type_row)
        
        # 스캔 버튼
        self.btn_scan = QPushButton("🔍 페이지 스캔")
        self.btn_scan.setObjectName("warning")
        self.btn_scan.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_scan.setMinimumHeight(40)
        self.btn_scan.clicked.connect(self._scan_page_elements)
        scan_settings_layout.addWidget(self.btn_scan)
        
        scan_settings_group.setLayout(scan_settings_layout)
        scan_inner_layout.addWidget(scan_settings_group)
        
        # 스캔 결과 테이블
        results_group = QGroupBox("📋 스캔 결과")
        results_layout = QVBoxLayout()
        results_layout.setContentsMargins(12, 10, 12, 10)
        
        self.table_scan_results = QTableWidget()
        self.table_scan_results.setColumnCount(4)
        self.table_scan_results.setHorizontalHeaderLabels(["XPath", "Tag", "Text", "사용"])
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

    def _create_status_panel(self):
        """상태 패널"""
        self.status_layout = QHBoxLayout()
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.status_layout.addWidget(self.progress_bar, 1)
        
        # 구분선
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setObjectName("separator")
        self.status_layout.addWidget(sep)
        
        # 폰트 크기 조절
        btn_zoom_out = QPushButton("-")
        btn_zoom_out.setFixedSize(24, 24)
        btn_zoom_out.clicked.connect(self._decrease_font)
        
        btn_zoom_in = QPushButton("+")
        btn_zoom_in.setFixedSize(24, 24)
        btn_zoom_in.clicked.connect(self._increase_font)
        
        self.status_layout.addWidget(QLabel("Font:"))
        self.status_layout.addWidget(btn_zoom_out)
        self.status_layout.addWidget(btn_zoom_in)

    def _setup_timers(self):
        """주기적 작업 타이머"""
        self.check_timer = QTimer(self)
        self.check_timer.timeout.connect(self._check_browser)
        self.check_timer.start(BROWSER_CHECK_INTERVAL)
