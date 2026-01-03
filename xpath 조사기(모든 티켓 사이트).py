#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
티켓 사이트 XPath 탐색기 v3.3
- 직관적인 UI/UX
- 실시간 요소 선택 및 XPath 추출
- 다중 사이트 프리셋 (인터파크, 멜론티켓, YES24, 티켓링크, 네이버 예약)
- 다중 윈도우/팝업 지원
- 다양한 내보내기 형식
- v3.3 신규: 배치 테스트, 즐겨찾기/태그, 매크로 생성, 네트워크 분석, 드래그정렬, 통계
"""

import sys
import os
import json
import time
import random
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit, QComboBox, QCheckBox,
    QTableWidget, QTableWidgetItem, QTabWidget, QSplitter, QGroupBox,
    QProgressBar, QMenu, QToolBar, QDialog, QDialogButtonBox,
    QListWidget, QListWidgetItem, QMessageBox, QFileDialog, QHeaderView,
    QAbstractItemView, QSpinBox, QFormLayout, QScrollArea, QFrame,
    QTreeWidget, QTreeWidgetItem, QPlainTextEdit, QStackedWidget,
    QToolButton, QGridLayout, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize, QSettings, QPropertyAnimation, QEasingCurve, QMimeData
from PyQt6.QtGui import QFont, QColor, QAction, QPalette, QIcon, QPixmap, QKeySequence, QDrag

# 사용자 모듈 임포트
from xpath_constants import APP_TITLE, APP_VERSION, SITE_PRESETS
from xpath_styles import STYLE
from xpath_config import XPathItem, SiteConfig
from xpath_widgets import ToastWidget
from xpath_browser import BrowserManager
from xpath_workers import PickerWatcher, ValidateWorker

# v3.3 신규 모듈
from xpath_codegen import CodeGenerator, CodeTemplate
from xpath_statistics import StatisticsManager

import logging

def setup_logger():
    """로거 설정"""
    logger = logging.getLogger('XPathExplorer')
    logger.setLevel(logging.DEBUG)
    
    # 콘솔 핸들러
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S')
    console_handler.setFormatter(console_format)
    
    # 파일 핸들러
    log_dir = Path.home() / '.xpath_explorer'
    log_dir.mkdir(exist_ok=True)
    file_handler = logging.FileHandler(
        log_dir / 'debug.log',
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter('%(asctime)s [%(levelname)s] %(funcName)s:%(lineno)d - %(message)s')
    file_handler.setFormatter(file_format)
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger

logger = setup_logger()


# ============================================================================
# 메인 윈도우
# ============================================================================

class XPathExplorer(QMainWindow):
    """XPath 탐색기 메인"""
    
    def __init__(self):
        super().__init__()
        
        self.browser = BrowserManager()
        self.config = SiteConfig.from_preset("인터파크")
        
        # v3.3 신규: 통계 관리자 및 코드 생성기
        self.stats_manager = StatisticsManager()
        self.code_generator = CodeGenerator()
        
        # 워커 스레드 관리
        self.picker_watcher = None
        self.validate_worker = None
        
        # 상태 변수
        self._font_size = 14
        self._search_text = ""
        self._filter_favorites_only = False  # v3.3: 즐겨찾기 필터
        self._filter_tag = ""  # v3.3: 태그 필터
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300) # [PERF-003] 300ms Debounce
        self._search_timer.timeout.connect(self._perform_search)
        
        self.init_settings()
        self._init_ui()
        self._load_settings()
        self._setup_timers()
        
    def init_settings(self):
        self.settings = QSettings("MyCompany", "XPathExplorer")
        
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
        
    def resizeEvent(self, event):
        """[BUG-002] 윈도우 리사이즈 시 Toast 위치 업데이트"""
        super().resizeEvent(event)
        if hasattr(self, 'toast') and self.toast.isVisible():
            self.toast._update_position()
            
    def _create_menu(self):
        """메뉴바"""
        menubar = self.menuBar()
        
        # 파일 메뉴
        file_menu = menubar.addMenu('파일(&F)')
        
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
        
        export_menu = file_menu.addMenu('내보내기(&E)')
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
        
        # 도구 메뉴
        tools_menu = menubar.addMenu('도구(&T)')
        
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
        
        cookies_menu = tools_menu.addMenu('쿠키 관리')
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
        batch_menu = tools_menu.addMenu('📊 배치 테스트')
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
        
        # v3.3 통계
        stats_action = QAction('📈 통계 보기', self)
        stats_action.triggered.connect(self._show_statistics)
        tools_menu.addAction(stats_action)
        
        # 보기 메뉴
        view_menu = menubar.addMenu('보기(&V)')
        
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
        help_menu = menubar.addMenu('도움말(&H)')
        
        shortcuts_action = QAction('단축키 목록(&K)', self)
        shortcuts_action.triggered.connect(self._show_shortcuts)
        help_menu.addAction(shortcuts_action)
        
        about_action = QAction('정보(&A)', self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _create_browser_panel(self):
        """브라우저 컨트롤 패널 - [UX] 개선"""
        self.browser_layout = QHBoxLayout()
        
        # 브라우저 제어 그룹
        self.btn_open = QPushButton("브라우저 열기")
        self.btn_open.setObjectName("primary")
        self.btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open.setToolTip("크롬 브라우저를 실행합니다.") # [UX-004] 툴팁
        self.btn_open.clicked.connect(self._toggle_browser)
        self.browser_layout.addWidget(self.btn_open)
        
        # 시각적 구분선 1
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.VLine)
        sep1.setObjectName("separator")
        self.browser_layout.addWidget(sep1)
        
        # 사이트 프리셋
        self.browser_layout.addWidget(QLabel("사이트:"))
        self.combo_preset = QComboBox()
        self.combo_preset.addItems(SITE_PRESETS.keys())
        # [BUG-004] 시그널 연결을 _on_preset_changed 에서 처리 (currentIndexChanged 대신 텍스트로)
        self.combo_preset.currentTextChanged.connect(self._on_preset_changed)
        self.browser_layout.addWidget(self.combo_preset)
        
        self.browser_layout.addWidget(QLabel("URL"))
        self.input_url = QLineEdit()
        self.input_url.setPlaceholderText("https://example.com")
        self.input_url.returnPressed.connect(self._navigate)
        self.browser_layout.addWidget(self.input_url, 1)
        
        self.btn_go = QPushButton("이동")
        self.btn_go.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_go.clicked.connect(self._navigate)
        self.browser_layout.addWidget(self.btn_go)
        
        # 시각적 구분선 2
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setObjectName("separator")
        self.browser_layout.addWidget(sep2)
        
        self.browser_layout.addWidget(QLabel("창:"))
        self.combo_windows = QComboBox()
        self.combo_windows.setMinimumWidth(150)
        self.combo_windows.currentIndexChanged.connect(self._on_window_changed)
        self.browser_layout.addWidget(self.combo_windows)
        
        self.btn_refresh_wins = QPushButton("🔄")
        self.btn_refresh_wins.setObjectName("icon_btn")
        self.btn_refresh_wins.setToolTip("창 목록 새로고침") # [UX-004]
        self.btn_refresh_wins.clicked.connect(self._refresh_windows)
        self.browser_layout.addWidget(self.btn_refresh_wins)
        
        # 시각적 구분선 3
        sep3 = QFrame()
        sep3.setFrameShape(QFrame.Shape.VLine)
        sep3.setObjectName("separator")
        self.browser_layout.addWidget(sep3)
        
        self.browser_layout.addWidget(QLabel("프레임:"))
        self.combo_frames = QComboBox()
        self.combo_frames.setMinimumWidth(150)
        self.browser_layout.addWidget(self.combo_frames)
        
        self.btn_scan_frames = QPushButton("🔍")
        self.btn_scan_frames.setObjectName("icon_btn")
        self.btn_scan_frames.setToolTip("iframe 스캔") # [UX-004]
        self.btn_scan_frames.clicked.connect(self._scan_frames)
        self.browser_layout.addWidget(self.btn_scan_frames)
        
        # 상태 표시용 라벨 (우측 끝)
        self.lbl_status = QLabel("● 대기 중")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_status.setMinimumWidth(100)
        self.lbl_status.setObjectName("status_disconnected")
        self.browser_layout.addWidget(self.lbl_status)

    def _create_list_panel(self):
        """XPath 목록 패널"""
        layout = QVBoxLayout(self.left_panel)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 헤더
        header_layout = QHBoxLayout()
        title = QLabel("XPath 목록")
        title.setObjectName("title")
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        btn_add = QPushButton("+ 새 항목")
        btn_add.setObjectName("primary")
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.setToolTip("새로운 빈 항목 추가 (Ctrl+N)")
        btn_add.clicked.connect(self._add_new_item)
        header_layout.addWidget(btn_add)
        layout.addLayout(header_layout)
        
        # 필터링 Row 1
        filter_layout = QHBoxLayout()
        self.combo_filter = QComboBox()
        self.combo_filter.addItem("전체")
        self.combo_filter.currentTextChanged.connect(lambda t: self._refresh_table(t))
        filter_layout.addWidget(self.combo_filter)
        
        # v3.3: 태그 필터
        self.combo_tag_filter = QComboBox()
        self.combo_tag_filter.addItem("모든 태그")
        self.combo_tag_filter.currentTextChanged.connect(self._on_tag_filter_changed)
        self.combo_tag_filter.setMinimumWidth(100)
        filter_layout.addWidget(self.combo_tag_filter)
        
        # v3.3: 즐겨찾기 필터
        self.chk_favorites_only = QCheckBox("⭐ 즐겨찾기만")
        self.chk_favorites_only.stateChanged.connect(self._on_favorites_filter_changed)
        filter_layout.addWidget(self.chk_favorites_only)
        
        # 검색 기능 개선 (Debounce 적용)
        self.input_search = QLineEdit()
        self.input_search.setPlaceholderText("🔍 검색 (이름, 설명, XPath)...")
        # [BUG-003] textChanged -> 타이머 시작 (Debounce)
        self.input_search.textChanged.connect(self._on_search_text_changed)
        filter_layout.addWidget(self.input_search, 2)
        
        layout.addLayout(filter_layout)
        
        # 테이블 - v3.3: 컬럼 확장 (즐겨찾기, 성공률 추가)
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["⭐", "", "이름", "카테고리", "설명", "성공률", ""])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
        # v3.3: 드래그 앤 드롭 활성화
        self.table.setDragEnabled(True)
        self.table.setAcceptDrops(True)
        self.table.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.table.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.table.setDropIndicatorShown(True)
        
        self.table.setColumnWidth(0, 30)   # 즐겨찾기
        self.table.setColumnWidth(1, 30)   # 상태 아이콘
        self.table.setColumnWidth(2, 140)  # 이름
        self.table.setColumnWidth(3, 90)   # 카테고리
        self.table.setColumnWidth(5, 60)   # 성공률
        self.table.setColumnWidth(6, 40)   # 삭제 버튼
        
        self.table.itemSelectionChanged.connect(self._on_item_selected)
        self.table.cellClicked.connect(self._on_cell_clicked)  # v3.3: 즐겨찾기 토글
        
        # 컨텍스트 메뉴
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        
        layout.addWidget(self.table)
        
        # 요약 정보
        self.lbl_summary = QLabel("총 0개")
        self.lbl_summary.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.lbl_summary.setObjectName("info_label")
        layout.addWidget(self.lbl_summary)

    def _create_editor_panel(self):
        """편집기 패널"""
        layout = QVBoxLayout(self.right_panel)
        layout.setContentsMargins(10, 0, 0, 0)
        
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
        layout.addWidget(group_picker)
        
        # 2. 상세 편집
        group_edit = QGroupBox("상세 편집")
        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        
        self.input_name = QLineEdit()
        self.input_name.setPlaceholderText("예: login_btn")
        form_layout.addRow(QLabel("이름:"), self.input_name)
        
        # 카테고리 (Editable ComboBox)
        self.input_category = QComboBox()
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
        layout.addWidget(group_edit)
        
        # 3. XPath & CSS
        group_code = QGroupBox("선택자 (Selectors)")
        code_layout = QVBoxLayout()
        
        # XPath
        code_layout.addWidget(QLabel("XPath:"))
        xpath_row = QHBoxLayout()
        self.input_xpath = QPlainTextEdit()
        self.input_xpath.setMaximumHeight(60)
        self.input_xpath.setPlaceholderText("//div[@id='example']")
        xpath_row.addWidget(self.input_xpath)
        
        # XPath 복사 버튼
        btn_copy_xpath = QPushButton("📋")
        btn_copy_xpath.setObjectName("icon_btn")
        btn_copy_xpath.setToolTip("XPath 복사")
        btn_copy_xpath.clicked.connect(self._copy_xpath)
        xpath_row.addWidget(btn_copy_xpath)
        
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
        layout.addWidget(group_code)
        
        # 4. 검증 결과
        group_result = QGroupBox("검증 결과")
        result_layout = QVBoxLayout()
        
        self.txt_result = QTextEdit()
        self.txt_result.setReadOnly(True)
        self.txt_result.setMaximumHeight(100)
        self.txt_result.setStyleSheet("background-color: #181825; color: #a6e3a1; font-family: 'Consolas', monospace; border: 1px solid #45475a;")
        result_layout.addWidget(self.txt_result)
        
        group_result.setLayout(result_layout)
        layout.addWidget(group_result)
        
        layout.addStretch()

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
        self.check_timer.start(2000)

    # =========================================================================
    # 로직 핸들러: 브라우저
    # =========================================================================

    def _check_browser(self):
        """브라우저 연결 상태 주기적 확인"""
        if self.browser.is_alive():
            self.lbl_status.setText(f"● 연결됨 ({self.config.name})")
            self.lbl_status.setObjectName("status_connected")
            self.btn_open.setText("브라우저 닫기")
            self.btn_open.setObjectName("danger")
            
            # 윈도우 목록이 비어있으면 갱신 (최초 연결 시)
            if self.combo_windows.count() == 0:
                self._refresh_windows()
        else:
            self.lbl_status.setText("● 연결 끊김")
            self.lbl_status.setObjectName("status_disconnected")
            self.btn_open.setText("브라우저 열기")
            self.btn_open.setObjectName("primary")
            self.combo_windows.clear()
            self.combo_frames.clear()
            
        # 스타일 리로드 (색상 변경 적용)
        self.lbl_status.style().unpolish(self.lbl_status)
        self.lbl_status.style().polish(self.lbl_status)
        self.btn_open.style().unpolish(self.btn_open)
        self.btn_open.style().polish(self.btn_open)

    def _toggle_browser(self):
        """브라우저 열기/닫기"""
        if self.browser.is_alive():
            self.browser.close()
            self._show_toast("브라우저가 종료되었습니다.", "info")
        else:
            # 설정의 URL 사용
            start_url = self.config.login_url or self.config.url
            if not start_url:
                start_url = "about:blank"
                
            self._show_toast("브라우저를 시작합니다...", "info", 5000)
            QApplication.processEvents()
            
            if self.browser.create_driver():
                self.browser.navigate(start_url)
                self.input_url.setText(start_url)
                self._refresh_windows()
                self._show_toast("브라우저가 실행되었습니다.", "success")
            else:
                self._show_toast("브라우저 실행 실패. 드라이버를 확인하세요.", "error")

    def _navigate(self):
        """URL 이동"""
        url = self.input_url.text().strip()
        if not url: return
        
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            
        if self.browser.is_alive():
            self.browser.navigate(url)
            self._show_toast(f"이동 중: {url}", "info")
        else:
            self._show_toast("브라우저가 실행되지 않았습니다.", "warning")

    def _refresh_windows(self):
        """윈도우 목록 갱신"""
        self.combo_windows.blockSignals(True)
        self.combo_windows.clear()
        
        windows = self.browser.get_windows()
        for i, win in enumerate(windows):
            title = win['title'] if win['title'] else f"Window {i+1}"
            if len(title) > 30: title = title[:27] + "..."
            
            self.combo_windows.addItem(f"{title}", win['handle'])
            
            if win['current']:
                self.combo_windows.setCurrentIndex(i)
                
        self.combo_windows.blockSignals(False)
        self._scan_frames() # 윈도우 갱신 시 프레임도 같이 스캔

    def _on_window_changed(self, index):
        """윈도우 전환"""
        if index < 0: return
        
        handle = self.combo_windows.itemData(index)
        if self.browser.switch_window(handle):
            self._scan_frames()
            self._show_toast("윈도우가 전환되었습니다.", "success")
        else:
            self._show_toast("윈도우 전환 실패", "error")
            self._refresh_windows()

    def _scan_frames(self):
        """iframe 목록 스캔"""
        self.combo_frames.clear()
        self.combo_frames.addItem("Main Content", "main")
        
        if not self.browser.is_alive():
            return
            
        frames = self.browser.get_all_frames()
        for path, identifier in frames:
            indent = "  " * path.count('/')
            self.combo_frames.addItem(f"{indent}📄 {identifier}", path)
            
        self._show_toast(f"{len(frames)}개의 프레임을 찾았습니다.", "info")

    # =========================================================================
    # 로직 핸들러: 데이터 & 편집
    # =========================================================================

    def _on_preset_changed(self, preset_name):
        """
        [BUG-004] 프리셋 변경 시 확인 로직 개선
        기존: 같은 프리셋을 다시 선택해도 변경 확인창 뜸
        수정: 현재 config.name과 다를 때만 확인
        """
        if preset_name == self.config.name:
            return

        if self.table.rowCount() > 0:
            reply = QMessageBox.question(
                self, '확인',
                f'"{preset_name}" 프리셋을 불러오시겠습니까?\n현재 작성 중인 목록은 초기화됩니다.',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                # 콤보박스를 이전 값으로 되돌려야 함 (구현 복잡성으로 인해 여기선 생략하고, 그냥 로드 취소)
                self.combo_preset.blockSignals(True)
                self.combo_preset.setCurrentText(self.config.name)
                self.combo_preset.blockSignals(False)
                return

        self.config = SiteConfig.from_preset(preset_name)
        
        # URL 입력창 업데이트
        if self.config.login_url:
            self.input_url.setText(self.config.login_url)
        elif self.config.url:
            self.input_url.setText(self.config.url)
            
        self._refresh_table()
        self._show_toast(f"{preset_name} 프리셋 로드 완료", "success")

    def _refresh_table(self, filter_cat=None):
        """테이블 갱신 - v3.3: 확장된 컬럼 및 필터 지원"""
        self.table.setRowCount(0)
        
        # 카테고리 필터 콤보박스 업데이트
        categories = sorted(self.config.get_categories())
        current_cat = self.combo_filter.currentText()
        
        self.combo_filter.blockSignals(True)
        self.combo_filter.clear()
        self.combo_filter.addItem("전체")
        self.combo_filter.addItems(categories)
        
        if current_cat in categories:
            self.combo_filter.setCurrentText(current_cat)
        self.combo_filter.blockSignals(False)
        
        # v3.3: 태그 필터 콤보박스 업데이트
        all_tags = set()
        for item in self.config.items:
            all_tags.update(item.tags)
        
        current_tag = self.combo_tag_filter.currentText()
        self.combo_tag_filter.blockSignals(True)
        self.combo_tag_filter.clear()
        self.combo_tag_filter.addItem("모든 태그")
        self.combo_tag_filter.addItems(sorted(all_tags))
        if current_tag in all_tags:
            self.combo_tag_filter.setCurrentText(current_tag)
        self.combo_tag_filter.blockSignals(False)
        
        # 실제 필터링 적용
        target_cat = filter_cat if filter_cat else self.combo_filter.currentText()
        
        items_to_show = []
        for item in self.config.items:
            # 1. 카테고리 필터
            if target_cat != "전체" and item.category != target_cat:
                continue
            
            # 2. 검색어 필터
            if self._search_text:
                st = self._search_text.lower()
                if (st not in item.name.lower() and 
                    st not in item.description.lower() and 
                    st not in item.xpath.lower()):
                    continue
            
            # v3.3: 즐겨찾기 필터
            if self._filter_favorites_only and not item.is_favorite:
                continue
            
            # v3.3: 태그 필터
            if self._filter_tag and self._filter_tag != "모든 태그":
                if self._filter_tag not in item.tags:
                    continue
            
            items_to_show.append(item)
        
        # v3.3: sort_order로 정렬
        items_to_show.sort(key=lambda x: x.sort_order)
            
        verified_count = 0
        
        for item in items_to_show:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # 컬럼 0: 즐겨찾기
            fav_item = QTableWidgetItem("⭐" if item.is_favorite else "☆")
            fav_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            fav_item.setToolTip("클릭하여 즐겨찾기 토글")
            self.table.setItem(row, 0, fav_item)
            
            # 컬럼 1: 상태
            status = QTableWidgetItem("✅" if item.is_verified else "⬜")
            status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 1, status)
            if item.is_verified: verified_count += 1
            
            # 컬럼 2: 이름
            name_item = QTableWidgetItem(item.name)
            name_item.setData(Qt.ItemDataRole.UserRole, item.name)  # 식별용
            self.table.setItem(row, 2, name_item)
            
            # 컬럼 3: 카테고리
            cat_item = QTableWidgetItem(item.category)
            cat_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            cat_item.setBackground(QColor("#313244"))
            self.table.setItem(row, 3, cat_item)
            
            # 컬럼 4: 설명
            desc_text = item.description
            if item.tags:
                desc_text += f" [{', '.join(item.tags)}]"
            self.table.setItem(row, 4, QTableWidgetItem(desc_text))
            
            # 컬럼 5: 성공률
            rate_text = f"{item.success_rate:.0f}%" if item.test_count > 0 else "-"
            rate_item = QTableWidgetItem(rate_text)
            rate_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            # 색상 표시
            if item.test_count > 0:
                if item.success_rate >= 80:
                    rate_item.setForeground(QColor("#a6e3a1"))  # Green
                elif item.success_rate >= 50:
                    rate_item.setForeground(QColor("#fab387"))  # Orange
                else:
                    rate_item.setForeground(QColor("#f38ba8"))  # Red
            self.table.setItem(row, 5, rate_item)
            
            # 컬럼 6: 삭제 버튼
            btn_del = QPushButton("🗑")
            btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_del.setStyleSheet("color: #f38ba8; font-weight: bold; border: none; background: transparent;")
            btn_del.clicked.connect(lambda _, n=item.name: self._delete_item(n))
            self.table.setCellWidget(row, 6, btn_del)

        self.lbl_summary.setText(f"총 {len(self.config.items)}개 (필터됨: {len(items_to_show)}개) | ✅ {verified_count}")

    def _on_search_text_changed(self, text):
        """[BUG-003] 검색어 변경 시 타이머 시작 (Debounce)"""
        self._search_text = text.strip()
        self._search_timer.start()
        
    def _perform_search(self):
        """Debounce 후 실제 검색"""
        self._refresh_table()
    
    # v3.3: 즐겨찾기 필터 핸들러
    def _on_favorites_filter_changed(self, state):
        """즐겨찾기 필터 변경"""
        self._filter_favorites_only = (state == Qt.CheckState.Checked.value)
        self._refresh_table()
    
    # v3.3: 태그 필터 핸들러
    def _on_tag_filter_changed(self, tag):
        """태그 필터 변경"""
        self._filter_tag = tag
        self._refresh_table()
    
    # v3.3: 셀 클릭 핸들러 (즐겨찾기 토글)
    def _on_cell_clicked(self, row, column):
        """셀 클릭 핸들러"""
        if column == 0:  # 즐겨찾기 컬럼
            item_name = self.table.item(row, 2).data(Qt.ItemDataRole.UserRole)
            item = self.config.get_item(item_name)
            if item:
                item.is_favorite = not item.is_favorite
                self._refresh_table()
                status = "추가" if item.is_favorite else "해제"
                self._show_toast(f"'{item.name}' 즐겨찾기 {status}", "success", 1500)

    def _on_item_selected(self):
        """테이블 항목 선택 시 에디터로 로드"""
        selected = self.table.selectedItems()
        if not selected: return
        
        row = selected[0].row()
        item_name = self.table.item(row, 2).data(Qt.ItemDataRole.UserRole)  # v3.3: 컬럼 2
        
        item = self.config.get_item(item_name)
        if item:
            self._load_to_editor(item)

    def _load_to_editor(self, item: XPathItem):
        self.input_name.setText(item.name)
        self.input_category.setCurrentText(item.category)
        self.input_desc.setText(item.description)
        self.input_xpath.setPlainText(item.xpath)
        self.input_css.setText(item.css_selector)
        # v3.3: 태그 로드
        self.input_tags.setText(", ".join(item.tags))
        
        # 결과창에 메타데이터 표시
        meta = f"Last Verified: {'Success' if item.is_verified else 'Not verified'}\n"
        if item.element_tag: meta += f"Tag: {item.element_tag}\n"
        if item.found_frame: meta += f"Frame: {item.found_frame}\n"
        # v3.3: 통계 표시
        if item.test_count > 0:
            meta += f"Tests: {item.test_count} (Success: {item.success_rate:.0f}%)\n"
        if item.last_tested:
            meta += f"Last Test: {item.last_tested[:10]}\n"
        
        self.txt_result.setPlainText(meta)

    def _add_new_item(self):
        """새 항목 추가 모드"""
        self._clear_editor()
        self.input_name.setFocus()
        self.table.clearSelection()

    def _clear_editor(self):
        self.input_name.clear()
        self.input_desc.clear()
        self.input_xpath.clear()
        self.input_css.clear()
        self.txt_result.clear()
        self.input_tags.clear()  # v3.3
        self.input_category.setCurrentText("common")

    def _save_item(self):
        """항목 저장 - v3.3: 태그 및 통계 보존"""
        name = self.input_name.text().strip()
        xpath = self.input_xpath.toPlainText().strip()
        
        if not name or not xpath:
            self._show_toast("이름과 XPath는 필수입니다.", "warning")
            return
        
        # 기존 항목이 있는지 확인 (통계 보존용)
        existing = self.config.get_item(name)
        
        # v3.3: 태그 파싱
        tags_text = self.input_tags.text().strip()
        tags = [t.strip() for t in tags_text.split(",") if t.strip()]
            
        item = XPathItem(
            name=name,
            xpath=xpath,
            category=self.input_category.currentText(),
            description=self.input_desc.text(),
            css_selector=self.input_css.text().strip(),
            tags=tags
        )
        
        # v3.3: 기존 항목의 메타데이터 보존
        if existing:
            item.is_favorite = existing.is_favorite
            item.test_count = existing.test_count
            item.success_count = existing.success_count
            item.last_tested = existing.last_tested
            item.sort_order = existing.sort_order
            item.is_verified = existing.is_verified
            item.element_tag = existing.element_tag
        
        # 현재 활성 프레임 정보가 있다면 저장 (테스트 후 저장 시 유용)
        if self.browser.current_frame_path:
             item.found_frame = self.browser.current_frame_path
             
        self.config.add_or_update(item)
        self._refresh_table()
        self._show_toast(f"'{name}' 저장 완료", "success")

    def _delete_item(self, name):
        """항목 삭제"""
        if QMessageBox.question(self, "삭제", f"'{name}' 항목을 삭제하시겠습니까?", 
                              QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.config.remove_item(name)
            self._refresh_table()
            self._clear_editor()

    # =========================================================================
    # 로직 핸들러: 테스트 및 검증
    # =========================================================================

    def _test_xpath(self):
        """XPath 단일 테스트"""
        xpath = self.input_xpath.toPlainText().strip()
        if not xpath: return
        
        if not self.browser.is_alive():
            self._show_toast("브라우저가 연결되지 않았습니다.", "error")
            return
            
        self._show_toast("XPath 검색 중...", "info")
        QApplication.processEvents()
        
        # 테스트 전 현재 선택된 프레임이 있다면 반영
        # (드롭다운에서 선택한 프레임 경로 사용)
        selected_frame_idx = self.combo_frames.currentIndex()
        if selected_frame_idx > 0:
            target_frame = self.combo_frames.itemData(selected_frame_idx)
            self.browser.switch_to_frame_by_path(target_frame)
            
        result = self.browser.validate_xpath(xpath)
        
        if result['found']:
            msg = f"✅ 발견! (Count: {result.get('count', 1)})"
            detail = f"Tag: {result.get('tag')}\nText: {result.get('text')}\nFrame: {result.get('frame_path')}"
            self.txt_result.setPlainText(msg + "\n" + detail)
            self._show_toast("요소를 찾았습니다!", "success")
            
            # 하이라이트
            if result.get('frame_path'):
                self.browser.highlight(xpath, frame_path=result['frame_path'])
            else:
                self.browser.highlight(xpath)
                
            # 검증 성공 상태 업데이트 (저장된 항목인 경우)
            name = self.input_name.text().strip()
            item = self.config.get_item(name)
            if item and item.xpath == xpath:
                item.is_verified = True
                item.element_tag = result.get('tag', '')
                item.found_frame = result.get('frame_path', '')
                self._refresh_table()
        else:
            self.txt_result.setPlainText(f"❌ 실패\n{result.get('msg')}")
            self._show_toast("요소를 찾을 수 없습니다.", "error")

    def _highlight_xpath(self):
        """현재 XPath 하이라이트"""
        xpath = self.input_xpath.toPlainText().strip()
        if xpath:
            self.browser.highlight(xpath)

    def _start_picker(self):
        """요소 선택기 시작"""
        if not self.browser.is_alive():
            self._show_toast("브라우저를 먼저 실행해주세요.", "warning")
            return
            
        self.picker_watcher = PickerWatcher(self.browser)
        self.picker_watcher.picked.connect(self._on_picked)
        self.picker_watcher.cancelled.connect(self._on_pick_cancelled)
        
        self.browser.start_picker(overlay_mode=self.chk_overlay.isChecked())
        self.picker_watcher.start()
        
        self._show_toast("요소 선택 모드 시작! 브라우저에서 요소를 클릭하세요. (ESC: 취소)", "info", 5000)
        self.hide() # 메인창 숨김

    def _on_picked(self, result):
        """요소 선택 완료"""
        self.show()
        self.picker_watcher.stop()
        
        if not result or not isinstance(result, dict):
            return

        xpath = result.get('xpath', '')
        css = result.get('css', '')
        tag = result.get('tag', '')
        text = result.get('text', '')
        frame = result.get('frame', 'main')
        
        # 에디터 채우기
        self.input_xpath.setPlainText(xpath)
        self.input_css.setText(css)
        self.input_desc.setText(f"Selected: {tag} ({text[:20]})")
        
        # 결과창 업데이트
        self.txt_result.setPlainText(f"Captured from: {frame}\nTag: {tag}\nText: {text}")
        
        self._show_toast("요소 정보가 캡처되었습니다.", "success")
        
        # 이름 자동 제안
        if not self.input_name.text():
            suggested_name = f"ui_{tag}"
            if "login" in text.lower() or "login" in xpath.lower():
                suggested_name = "login_elem"
            self.input_name.setText(suggested_name)
            
        # 히스토리 추가
        self._add_to_history(xpath, css, tag, frame)

    def _on_pick_cancelled(self):
        """요소 선택 취소"""
        self.show()
        if self.picker_watcher:
            self.picker_watcher.stop()
        self._show_toast("요소 선택이 취소되었습니다.", "warning")

    def _validate_all(self):
        """전체 검증 시작"""
        if not self.config.items:
            self._show_toast("검증할 항목이 없습니다.", "warning")
            return
            
        if not self.browser.is_alive():
            self._show_toast("브라우저 연결 필요", "error")
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # 현재 열린 모든 윈도우 핸들 수집 (워커에 전달용)
        windows = [w['handle'] for w in self.browser.get_windows()]
        
        self.validate_worker = ValidateWorker(self.browser, self.config.items, windows)
        self.validate_worker.progress.connect(lambda v, m: (self.progress_bar.setValue(v), self.lbl_status.setText(m)))
        self.validate_worker.validated.connect(self._on_validated)
        self.validate_worker.finished.connect(self._on_validate_finished)
        self.validate_worker.start()

    def _on_validated(self, name, result):
        """개별 검증 결과 처리"""
        item = self.config.get_item(name)
        if item:
            item.is_verified = result['found']
            if result['found']:
                item.element_tag = result.get('tag', '')
                item.found_frame = result.get('frame_path', '')

    def _on_validate_finished(self, found, total):
        """검증 완료"""
        self.progress_bar.setVisible(False)
        self._refresh_table()
        self._show_toast(f"검증 완료: {found}/{total} 성공", "success" if found==total else "warning")
        self.validate_worker = None

    # =========================================================================
    # 유틸리티
    # =========================================================================

    def _show_toast(self, message, toast_type="info", duration=3000):
        self.toast.show_toast(message, toast_type, duration)

    def _copy_xpath(self):
        xpath = self.input_xpath.toPlainText().strip()
        if xpath:
            QApplication.clipboard().setText(xpath)
            self._show_toast("XPath 복사됨", "success", 1500)

    def _copy_css(self):
        css = self.input_css.text().strip()
        if css:
            QApplication.clipboard().setText(css)
            self._show_toast("CSS 복사됨", "success", 1500)

    def _new_config(self):
        if QMessageBox.question(self, "새 설정", "모든 항목을 지우고 초기화하시겠습니까?") == QMessageBox.StandardButton.Yes:
            self.config = SiteConfig.from_preset("빈 템플릿")
            self._refresh_table()
            self._clear_editor()

    def _open_config(self):
        fname, _ = QFileDialog.getOpenFileName(self, '설정 열기', '', 'JSON Files (*.json)')
        if fname:
            try:
                with open(fname, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.config = SiteConfig.from_dict(data)
                    self._refresh_table()
                    self._show_toast("설정을 불러왔습니다.", "success")
            except Exception as e:
                self._show_toast(f"로드 실패: {e}", "error")

    def _save_config(self):
        fname, _ = QFileDialog.getSaveFileName(self, '설정 저장', f"{self.config.name}.json", 'JSON Files (*.json)')
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
            self._show_toast("내보낼 항목이 없습니다.", "warning")
            return
            
        fname, _ = QFileDialog.getSaveFileName(self, f'{fmt.upper()}로 내보내기', f"xpath_export", f'{fmt.upper()} Files (*.{fmt})')
        if not fname: return
        
        try:
            content = ""
            if fmt == 'json':
                data = [item.to_dict() for item in self.config.items]
                content = json.dumps(data, indent=2, ensure_ascii=False)
            elif fmt == 'csv':
                content = "Name,XPath,Category,Description\n"
                for item in self.config.items:
                    content += f"{item.name},{item.xpath},{item.category},{item.description}\n"
            elif fmt == 'python':
                content = "# Selenium XPaths\n\nclass XPaths:\n"
                for item in self.config.items:
                    safe_name = item.name.replace(' ', '_').upper()
                    content += f"    {safe_name} = \"{item.xpath}\"  # {item.description}\n"
            elif fmt == 'javascript':
                content = "const XPaths = {\n"
                for item in self.config.items:
                    content += f"    '{item.name}': '{item.xpath}', // {item.description}\n"
                content += "};"
                
            with open(fname, 'w', encoding='utf-8') as f:
                f.write(content)
                
            self._show_toast(f"{fmt.upper()} 내보내기 성공", "success")
            
        except Exception as e:
            self._show_toast(f"내보내기 실패: {e}", "error")

    # 폰트 제어
    def _increase_font(self):
        self._apply_font_size(self._font_size + 1)
        
    def _decrease_font(self):
        self._apply_font_size(self._font_size - 1)
        
    def _reset_font(self):
        self._apply_font_size(14)
        
    def _apply_font_size(self, size):
        self._font_size = max(8, min(size, 24))
        font = self.font()
        font.setPointSize(self._font_size)
        QApplication.instance().setFont(font)
        self._show_toast(f"폰트 크기: {self._font_size}", "info", 1000)

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        
        edit_action = QAction("✏️ 편집", self)
        edit_action.triggered.connect(self._on_item_selected)
        menu.addAction(edit_action)
        
        copy_action = QAction("📋 XPath 복사", self)
        copy_action.triggered.connect(lambda: self._copy_from_table_context(0))
        menu.addAction(copy_action)
        
        delete_action = QAction("🗑 삭제", self)
        delete_action.triggered.connect(self._delete_selected)
        menu.addAction(delete_action)
        
        menu.exec(self.table.viewport().mapToGlobal(pos))
        
    def _copy_from_table_context(self, type_idx):
        selected = self.table.selectedItems()
        if not selected: return
        item_name = self.table.item(selected[0].row(), 1).data(Qt.ItemDataRole.UserRole)
        item = self.config.get_item(item_name)
        if item:
            QApplication.clipboard().setText(item.xpath)
            self._show_toast("복사되었습니다.", "success")

    def _delete_selected(self):
        selected = self.table.selectedItems()
        if not selected: return
        item_name = self.table.item(selected[0].row(), 1).data(Qt.ItemDataRole.UserRole)
        self._delete_item(item_name)
        
    def _show_shortcuts(self):
        shortcuts = [
            ("Ctrl+N", "새 설정"),
            ("Ctrl+O", "설정 열기"),
            ("Ctrl+S", "설정 저장"),
            ("Ctrl+T", "현재 XPath 테스트"),
            ("Ctrl+H", "XPath 히스토리"),
            ("F5", "전체 유효성 검사"),
            ("Ctrl++", "폰트 크게"),
            ("Ctrl+-", "폰트 작게")
        ]
        msg = "\n".join([f"{k}: {v}" for k, v in shortcuts])
        QMessageBox.information(self, "단축키 목록", msg)

    def _show_about(self):
        QMessageBox.about(self, "정보", f"{APP_TITLE}\n\n티켓 예매 사이트 자동화를 위한 XPath 도구입니다.")

    def _show_xpath_history(self):
        """[BUG-005] 히스토리 중복 제거된 목록 표시"""
        history = self._load_xpath_history_data()
        if not history:
            self._show_toast("히스토리가 비어있습니다.", "info")
            return
            
        dialog = QDialog(self)
        dialog.setWindowTitle("XPath 히스토리")
        dialog.resize(600, 400)
        
        layout = QVBoxLayout(dialog)
        
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["날짜", "Tag", "XPath", "Frame"])
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        
        # 최신순 정렬
        for row_data in reversed(history):
            row = table.rowCount()
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(row_data.get('time', '')))
            table.setItem(row, 1, QTableWidgetItem(row_data.get('tag', '')))
            table.setItem(row, 2, QTableWidgetItem(row_data.get('xpath', '')))
            table.setItem(row, 3, QTableWidgetItem(row_data.get('frame', 'main')))
            
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.doubleClicked.connect(lambda: self._use_history_item(table, dialog))
        
        layout.addWidget(table)
        
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_use = btn_box.addButton("선택 사용", QDialogButtonBox.ButtonRole.AcceptRole)
        btn_clear = btn_box.addButton("모두 지우기", QDialogButtonBox.ButtonRole.ResetRole)
        
        btn_box.rejected.connect(dialog.reject)
        btn_use.clicked.connect(lambda: self._use_history_item(table, dialog))
        btn_clear.clicked.connect(lambda: self._clear_history(dialog))
        
        layout.addWidget(btn_box)
        dialog.exec()

    def _add_to_history(self, xpath, css, tag, frame):
        """[BUG-005] 중복 방지하며 히스토리 추가"""
        history = self._load_xpath_history_data()
        
        new_entry = {
            "xpath": xpath,
            "css": css,
            "tag": tag,
            "frame": frame,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # 중복 검사 (최근 10개만 검사해도 충분)
        is_duplicate = False
        for entry in history[-10:]:
            if entry['xpath'] == xpath and entry['frame'] == frame:
                is_duplicate = True
                break
        
        if not is_duplicate:
            history.append(new_entry)
            # 최대 100개 유지
            if len(history) > 100:
                history = history[-100:]
            self._save_xpath_history_data(history)

    def _load_xpath_history_data(self):
        return self.settings.value("xpath_history", [])

    def _save_xpath_history_data(self, history):
        self.settings.setValue("xpath_history", history)

    def _use_history_item(self, table, dialog):
        selected = table.selectedItems()
        if not selected: return
        
        row = selected[0].row()
        xpath = table.item(row, 2).text()
        frame = table.item(row, 3).text()
        
        self.input_xpath.setPlainText(xpath)
        self._show_toast("히스토리에서 불러왔습니다.", "success")
        dialog.accept()

    def _clear_history(self, dialog):
        if QMessageBox.question(dialog, "확인", "히스토리를 모두 삭제하시겠습니까?") == QMessageBox.StandardButton.Yes:
            self._save_xpath_history_data([])
            dialog.reject()
            self._show_toast("히스토리가 삭제되었습니다.", "success")

    def _load_settings(self):
        """설정 로드"""
        geo = self.settings.value("geometry")
        if geo: self.restoreGeometry(geo)
        
        # 폰트 로드
        # ...

    def _save_cookies(self):
        """쿠키 저장"""
        if not self.browser.is_alive(): return
        fname, _ = QFileDialog.getSaveFileName(self, '쿠키 저장', 'cookies.json', 'JSON (*.json)')
        if fname:
            try:
                cookies = self.browser.driver.get_cookies()
                with open(fname, 'w') as f:
                    json.dump(cookies, f)
                self._show_toast(f"쿠키 {len(cookies)}개 저장됨", "success")
            except Exception as e:
                self._show_toast(f"실패: {e}", "error")

    def _load_cookies(self):
        """쿠키 로드"""
        if not self.browser.is_alive(): return
        fname, _ = QFileDialog.getOpenFileName(self, '쿠키 열기', '', 'JSON (*.json)')
        if fname:
            try:
                with open(fname, 'r') as f:
                    cookies = json.load(f)
                for cookie in cookies:
                    try:
                        self.browser.driver.add_cookie(cookie)
                    except: pass
                self._show_toast(f"쿠키 {len(cookies)}개 로드됨", "success")
                self.browser.driver.refresh()
            except Exception as e:
                self._show_toast(f"실패: {e}", "error")

    def _clear_cookies(self):
        if self.browser.is_alive():
            self.browser.driver.delete_all_cookies()
            self._show_toast("모든 쿠키가 삭제되었습니다.", "success")
    
    # =========================================================================
    # v3.3 신규 기능: 배치 테스트
    # =========================================================================
    
    def _batch_test(self, category: str = None):
        """배치 테스트 실행"""
        if not self.browser.is_alive():
            self._show_toast("브라우저를 먼저 연결해주세요.", "warning")
            return
        
        # 테스트할 항목 필터링
        items_to_test = self.config.items
        if category and category != "전체":
            items_to_test = [i for i in items_to_test if i.category == category]
        
        if not items_to_test:
            self._show_toast("테스트할 항목이 없습니다.", "warning")
            return
        
        self._show_toast(f"{len(items_to_test)}개 항목 배치 테스트 시작...", "info")
        
        # 프로그레스 표시
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        results = []
        for i, item in enumerate(items_to_test):
            progress = int((i / len(items_to_test)) * 100)
            self.progress_bar.setValue(progress)
            QApplication.processEvents()
            
            result = self.browser.validate_xpath(item.xpath)
            success = result.get('found', False)
            
            # 통계 기록
            item.record_test(success)
            self.stats_manager.record_test(item.name, item.xpath, success)
            
            results.append({
                'name': item.name,
                'success': success,
                'xpath': item.xpath,
                'msg': result.get('msg', '')
            })
            
            time.sleep(0.1)  # UI 응답성
        
        self.progress_bar.setVisible(False)
        self._refresh_table()
        
        # 결과 리포트 표시
        self._show_batch_report(results)
    
    def _batch_test_dialog(self):
        """카테고리 선택 후 배치 테스트"""
        categories = ["전체"] + sorted(self.config.get_categories())
        
        from PyQt6.QtWidgets import QInputDialog
        category, ok = QInputDialog.getItem(
            self, "배치 테스트", "테스트할 카테고리 선택:",
            categories, 0, False
        )
        if ok:
            self._batch_test(category)
    
    def _show_batch_report(self, results: list):
        """배치 테스트 결과 리포트"""
        dialog = QDialog(self)
        dialog.setWindowTitle("배치 테스트 결과")
        dialog.resize(700, 500)
        
        layout = QVBoxLayout(dialog)
        
        # 요약
        total = len(results)
        success_count = sum(1 for r in results if r['success'])
        success_rate = (success_count / total * 100) if total > 0 else 0
        
        summary = QLabel(f"총 {total}개 테스트 | ✅ 성공: {success_count} | ❌ 실패: {total - success_count} | 성공률: {success_rate:.1f}%")
        summary.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px;")
        layout.addWidget(summary)
        
        # 결과 테이블
        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["상태", "이름", "결과"])
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        
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
    
    # =========================================================================
    # v3.3 신규 기능: 매크로 생성
    # =========================================================================
    
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
        combo_template.addItems(["Selenium (Python)", "Playwright (Python)", "PyAutoGUI"])
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
            code = self.code_generator.generate(self.config.items, template)
            txt_code.setPlainText(code)
        
        combo_template.currentIndexChanged.connect(generate_code)
        generate_code()  # 초기 생성
        
        # 버튼
        btn_layout = QHBoxLayout()
        
        btn_copy = QPushButton("📋 복사")
        btn_copy.clicked.connect(lambda: (
            QApplication.clipboard().setText(txt_code.toPlainText()),
            self._show_toast("코드가 클립보드에 복사되었습니다.", "success")
        ))
        btn_layout.addWidget(btn_copy)
        
        btn_save = QPushButton("💾 파일로 저장")
        def save_code():
            ext = ".py" if combo_template.currentIndex() < 2 else ".py"
            fname, _ = QFileDialog.getSaveFileName(dialog, "코드 저장", "macro_script", f"Python (*.py)")
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
    
    # =========================================================================
    # v3.3 신규 기능: 네트워크 분석
    # =========================================================================
    
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
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(table)
        
        # 이벤트 핸들러
        def start_capture():
            url = input_url.text().strip()
            if not url:
                return
            
            lbl_status.setText("● 브라우저 시작 중...")
            QApplication.processEvents()
            
            if analyzer.start_browser(url, headless=False):
                analyzer.start_capture()
                lbl_status.setText("● 캡처 중... (페이지 조작 후 중지)")
                lbl_status.setStyleSheet("color: #a6e3a1;")
                btn_start.setEnabled(False)
                btn_stop.setEnabled(True)
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
            if analyzer._browser:
                analyzer.close()
            dialog.reject()
        
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(on_close)
        layout.addWidget(btn_close)
        
        dialog.exec()
    
    # =========================================================================
    # v3.3 신규 기능: 통계 보기
    # =========================================================================
    
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
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        
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

    def closeEvent(self, event):
        """종료 처리"""
        self.settings.setValue("geometry", self.saveGeometry())
        
        if self.picker_watcher:
            self.picker_watcher.stop()
            self.picker_watcher.wait(1000)
            
        if self.validate_worker:
            self.validate_worker.cancel()
            self.validate_worker.wait(1000)
            
        self.browser.close()
        event.accept()

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # 고해상도 지원
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    
    window = XPathExplorer()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
