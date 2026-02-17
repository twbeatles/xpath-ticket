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
from xpath_perf import perf_span

# v3.3 신규 모듈
from xpath_codegen import CodeGenerator, CodeTemplate
from xpath_statistics import StatisticsManager

# v4.0 신규 모듈
from xpath_optimizer import XPathOptimizer, XPathAlternative
from xpath_history import HistoryManager
from xpath_ai import XPathAIAssistant
from xpath_diff import XPathDiffAnalyzer

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
        
        # v3.4 신규: Playwright 매니저 (자동 요소 탐색용)
        self.pw_manager = None  # 지연 초기화
        
        # v4.0 신규 모듈
        self.optimizer = XPathOptimizer()
        self.history_manager = HistoryManager()
        self.ai_assistant = XPathAIAssistant()
        self.diff_analyzer = XPathDiffAnalyzer()
        
        # 워커 스레드 관리
        self.picker_watcher = None
        self.validate_worker = None
        self.live_preview_worker = None
        self.ai_worker = None
        self.diff_worker = None
        self.batch_worker = None
        self._live_preview_request_id = 0
        self._ai_request_id = 0
        
        # 상태 변수
        self._font_size = 14
        self._search_text = ""
        self._filter_favorites_only = False  # v3.3: 즐겨찾기 필터
        self._filter_tag = ""  # v3.3: 태그 필터
        self._filter_options_dirty = True
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(SEARCH_DEBOUNCE_MS)
        self._search_timer.timeout.connect(self._perform_search)
        
        # v4.0: 실시간 미리보기 타이머
        self._live_preview_timer = QTimer()
        self._live_preview_timer.setSingleShot(True)
        self._live_preview_timer.setInterval(LIVE_PREVIEW_DEBOUNCE_MS)
        self._live_preview_timer.timeout.connect(self._update_live_preview)
        
        self.init_settings()
        self._init_ui()
        self._load_settings()
        self._setup_timers()
        self._refresh_table(refresh_filters=True)
        
        # v4.0: 히스토리 초기화
        self.history_manager.initialize(self.config.items)
        
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
        
        # v4.0 편집 메뉴 (Undo/Redo)
        edit_menu = menubar.addMenu('편집(&E)')
        
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
        self.btn_back.clicked.connect(lambda: self.browser.driver.back() if self.browser.is_alive() else None)
        self.browser_layout.addWidget(self.btn_back)
        
        self.btn_forward = QPushButton("▶")
        self.btn_forward.setObjectName("icon_btn")
        self.btn_forward.setToolTip("앞으로가기")
        self.btn_forward.setFixedSize(26, 26)
        self.btn_forward.clicked.connect(lambda: self.browser.driver.forward() if self.browser.is_alive() else None)
        self.browser_layout.addWidget(self.btn_forward)
        
        self.btn_refresh_page = QPushButton("↻")
        self.btn_refresh_page.setObjectName("icon_btn")
        self.btn_refresh_page.setToolTip("페이지 새로고침")
        self.btn_refresh_page.setFixedSize(26, 26)
        self.btn_refresh_page.clicked.connect(lambda: self.browser.driver.refresh() if self.browser.is_alive() else None)
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
        self.table_scan_results.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table_scan_results.setColumnWidth(1, 60)
        self.table_scan_results.setColumnWidth(2, 120)
        self.table_scan_results.setColumnWidth(3, 60)
        self.table_scan_results.verticalHeader().setVisible(False)
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

    # =========================================================================
    # 로직 핸들러: 브라우저
    # =========================================================================

    def _check_browser(self):
        """브라우저 연결 상태 주기적 확인 (v3.6: AnimatedStatusIndicator 사용)"""
        is_alive = self.browser.is_alive()
        current_state = getattr(self, '_last_browser_state', None)
        
        # 상태 변경 시에만 UI 업데이트
        if current_state == is_alive:
            return
            
        self._last_browser_state = is_alive
        
        # AnimatedStatusIndicator 업데이트
        self.status_indicator.set_connected(is_alive)
        
        if is_alive:
            self.lbl_status.setText(f"{self.config.name}")
            self.lbl_status.setObjectName("status_connected")
            self.btn_open.setText("🔴 브라우저 닫기")
            self.btn_open.setObjectName("danger")
            
            # 윈도우 목록이 비어있으면 갱신 (최초 연결 시)
            if self.combo_windows.count() == 0:
                self._refresh_windows()
        else:
            self.lbl_status.setText("연결 안됨")
            self.lbl_status.setObjectName("status_disconnected")
            self.btn_open.setText("🌐 브라우저 열기")
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
            self.input_url.setText(url)  # 정규화된 URL로 입력창 업데이트
            
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
        with perf_span("ui.scan_frames"):
            self.combo_frames.blockSignals(True)
            try:
                self.combo_frames.clear()
                self.combo_frames.addItem("Main Content", "main")
                
                if not self.browser.is_alive():
                    return
                    
                frames = self.browser.get_all_frames()
                for path, identifier in frames:
                    indent = "  " * path.count('/')
                    self.combo_frames.addItem(f"{indent}📄 {identifier}", path)
                self._show_toast(f"{len(frames)}개의 프레임을 찾았습니다.", "info")
            finally:
                self.combo_frames.blockSignals(False)

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

        self._filter_options_dirty = True
        self._refresh_table(refresh_filters=True)
        self._show_toast(f"{preset_name} 프리셋 로드 완료", "success")

    def _refresh_filter_options_if_dirty(self, force: bool = False):
        """필터 옵션(카테고리/태그)을 필요할 때만 갱신."""
        if not (force or self._filter_options_dirty):
            return

        categories = sorted(self.config.get_categories())
        current_cat = self.combo_filter.currentText() or "전체"
        self.combo_filter.blockSignals(True)
        self.combo_filter.clear()
        self.combo_filter.addItem("전체")
        self.combo_filter.addItems(categories)
        if current_cat == "전체" or current_cat in categories:
            self.combo_filter.setCurrentText(current_cat)
        else:
            self.combo_filter.setCurrentIndex(0)
        self.combo_filter.blockSignals(False)

        all_tags = set()
        for item in self.config.items:
            all_tags.update(item.tags)

        current_tag = self.combo_tag_filter.currentText() or "모든 태그"
        self.combo_tag_filter.blockSignals(True)
        self.combo_tag_filter.clear()
        self.combo_tag_filter.addItem("모든 태그")
        self.combo_tag_filter.addItems(sorted(all_tags))
        if current_tag == "모든 태그" or current_tag in all_tags:
            self.combo_tag_filter.setCurrentText(current_tag)
        else:
            self.combo_tag_filter.setCurrentIndex(0)
        self.combo_tag_filter.blockSignals(False)

        self._filter_options_dirty = False

    def _item_matches_filters(self, item: XPathItem, target_cat: str) -> bool:
        if target_cat != "전체" and item.category != target_cat:
            return False

        if self._search_text:
            st = self._search_text.lower()
            if (
                st not in item.name.lower()
                and st not in item.description.lower()
                and st not in item.xpath.lower()
            ):
                return False

        if self._filter_favorites_only and not item.is_favorite:
            return False

        if self._filter_tag and self._filter_tag != "모든 태그":
            if self._filter_tag not in item.tags:
                return False

        return True

    def _collect_filtered_items(self, target_cat: str) -> List[XPathItem]:
        items_to_show = [item for item in self.config.items if self._item_matches_filters(item, target_cat)]
        items_to_show.sort(key=lambda x: x.sort_order)
        return items_to_show

    def _render_table_row(self, row: int, item: XPathItem):
        """단일 행 렌더링."""
        fav_item = QTableWidgetItem("⭐" if item.is_favorite else "☆")
        fav_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        fav_item.setToolTip("클릭하여 즐겨찾기 토글")
        self.table.setItem(row, 0, fav_item)

        status = QTableWidgetItem("✅" if item.is_verified else "⬜")
        status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, 1, status)

        name_item = QTableWidgetItem(item.name)
        name_item.setData(Qt.ItemDataRole.UserRole, item.name)
        self.table.setItem(row, 2, name_item)

        cat_item = QTableWidgetItem(item.category)
        cat_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        cat_item.setBackground(QColor("#313244"))
        self.table.setItem(row, 3, cat_item)

        desc_text = item.description
        if item.tags:
            desc_text += f" [{', '.join(item.tags)}]"
        self.table.setItem(row, 4, QTableWidgetItem(desc_text))

        rate_text = f"{item.success_rate:.0f}%" if item.test_count > 0 else "-"
        rate_item = QTableWidgetItem(rate_text)
        rate_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if item.test_count > 0:
            if item.success_rate >= 80:
                rate_item.setForeground(QColor("#a6e3a1"))
            elif item.success_rate >= 50:
                rate_item.setForeground(QColor("#fab387"))
            else:
                rate_item.setForeground(QColor("#f38ba8"))
        self.table.setItem(row, 5, rate_item)

        btn_del = QPushButton("🗑")
        btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_del.setStyleSheet("color: #f38ba8; font-weight: bold; border: none; background: transparent;")
        btn_del.clicked.connect(lambda _, n=item.name: self._delete_item(n))
        self.table.setCellWidget(row, 6, btn_del)

    def _render_table_rows(self, items_to_show: List[XPathItem]):
        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)
        try:
            self.table.setRowCount(len(items_to_show))
            for row, item in enumerate(items_to_show):
                self._render_table_row(row, item)
        finally:
            self.table.blockSignals(False)
            self.table.setUpdatesEnabled(True)

    def _update_table_summary(self, items_to_show: List[XPathItem]):
        verified_count = sum(1 for item in items_to_show if item.is_verified)
        self.lbl_summary.setText(f"총 {len(self.config.items)}개 (필터됨: {len(items_to_show)}개) | ✅ {verified_count}")
        if len(items_to_show) == 0 and len(self.config.items) > 0:
            self.lbl_summary.setText(f"검색 결과 없음 (전체: {len(self.config.items)}개)")
        elif len(self.config.items) == 0:
            self.lbl_summary.setText("항목이 없습니다. '+ 새 항목' 버튼을 클릭하여 추가하세요.")

    def _refresh_table(self, filter_cat=None, refresh_filters: bool = False):
        """테이블 갱신 - 필터 옵션/행 렌더링 분리."""
        with perf_span("ui.refresh_table"):
            self._refresh_filter_options_if_dirty(force=refresh_filters)
            target_cat = filter_cat if filter_cat is not None else self.combo_filter.currentText()
            items_to_show = self._collect_filtered_items(target_cat)
            self._render_table_rows(items_to_show)
            self._update_table_summary(items_to_show)
            return items_to_show

    def _on_search_text_changed(self, text):
        """[BUG-003] 검색어 변경 시 타이머 시작 (Debounce)"""
        self._search_text = text.strip()
        self._search_timer.start()
        # X 버튼 표시/숨김
        self.btn_clear_search.setVisible(bool(text.strip()))
        
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
                target_cat = self.combo_filter.currentText()
                if self._item_matches_filters(item, target_cat):
                    self._render_table_row(row, item)
                    self._update_table_summary(self._collect_filtered_items(target_cat))
                else:
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
        """항목 저장 - v3.3: 태그 및 통계 보존, v4.0: 히스토리 기록"""
        name = self.input_name.text().strip()
        xpath = self.input_xpath.toPlainText().strip()
        
        if not name or not xpath:
            self._show_toast("이름과 XPath는 필수입니다.", "warning")
            return
        
        # 기존 항목이 있는지 확인 (통계 보존용)
        existing = self.config.get_item(name)
        
        # v4.0: 변경 전 상태 히스토리에 저장
        action = "update" if existing else "add"
        self.history_manager.push_state(
            self.config.items, action, name,
            f"{name} 항목 {'수정' if existing else '추가'}"
        )
        
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
        self._filter_options_dirty = True
        self._refresh_table(refresh_filters=True)
        self._update_undo_redo_actions()  # v4.0
        # 히스토리 현재 상태 동기화 (변경 후)
        self.history_manager.sync_current_state(self.config.items)
        self._show_toast(f"'{name}' 저장 완료", "success")

    def _delete_item(self, name):
        """항목 삭제 - v4.0: 히스토리 기록"""
        if QMessageBox.question(self, "삭제", f"'{name}' 항목을 삭제하시겠습니까?", 
                              QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            # v4.0: 삭제 전 히스토리 저장
            self.history_manager.push_state(
                self.config.items, "delete", name,
                f"{name} 항목 삭제"
            )
            self.config.remove_item(name)
            self._filter_options_dirty = True
            self._refresh_table(refresh_filters=True)
            self._clear_editor()
            self._update_undo_redo_actions()  # v4.0
            # 히스토리 현재 상태 동기화 (변경 후)
            self.history_manager.sync_current_state(self.config.items)

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
        
        original_frame = self.browser.current_frame_path

        # 테스트 전 현재 선택된 프레임이 있다면 반영
        selected_frame_idx = self.combo_frames.currentIndex()
        target_frame = None
        if selected_frame_idx > 0:
            target_frame = self.combo_frames.itemData(selected_frame_idx)
            self.browser.switch_to_frame_by_path(target_frame)
        
        try:
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
                    item.record_test(True)  # 통계 기록
                    self._refresh_table()
            else:
                self.txt_result.setPlainText(f"❌ 실패\n{result.get('msg')}")
                self._show_toast("요소를 찾을 수 없습니다.", "error")
                # 실패 통계 기록
                name = self.input_name.text().strip()
                item = self.config.get_item(name)
                if item and item.xpath == xpath:
                    item.record_test(False)
        finally:
            # 프레임 복구 (항상 원복)
            try:
                self.browser.switch_to_frame_by_path(original_frame if original_frame else "main")
            except Exception:
                pass

    def _highlight_xpath(self):
        """현재 XPath 하이라이트"""
        xpath = self.input_xpath.toPlainText().strip()
        if not xpath:
            return
        if not self.browser.is_alive():
            self._show_toast("브라우저가 연결되지 않았습니다.", "warning")
            return
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
        if self.picker_watcher:
            self.picker_watcher.stop()
            self.picker_watcher.wait(WORKER_WAIT_TIMEOUT)
            self.picker_watcher = None
        
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
            self.picker_watcher.wait(WORKER_WAIT_TIMEOUT)
            self.picker_watcher = None
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
            item.record_test(result['found'])  # 통계 기록
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
            self._filter_options_dirty = True
            self._refresh_table(refresh_filters=True)
            self._clear_editor()

    def _open_config(self):
        fname, _ = QFileDialog.getOpenFileName(self, '설정 열기', '', 'JSON Files (*.json)')
        if fname:
            try:
                with open(fname, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.config = SiteConfig.from_dict(data)
                    self._filter_options_dirty = True
                    self._refresh_table(refresh_filters=True)
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
        item_name = self.table.item(selected[0].row(), 2).data(Qt.ItemDataRole.UserRole)
        item = self.config.get_item(item_name)
        if item:
            QApplication.clipboard().setText(item.xpath)
            self._show_toast("복사되었습니다.", "success")

    def _delete_selected(self):
        selected = self.table.selectedItems()
        if not selected: return
        item_name = self.table.item(selected[0].row(), 2).data(Qt.ItemDataRole.UserRole)
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
                    except Exception:
                        pass  # 개별 쿠키 추가 실패 시 무시
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
        item = self.config.get_item(name)
        if item:
            item.record_test(success)
        self.stats_manager.record_test(name, xpath, success, error_msg=msg if not success else "")

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
        if ok:
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

    # =========================================================================
    # v3.4 신규: Playwright 자동 요소 탐색
    # =========================================================================
    
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
                        QApplication.processEvents()
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
        
        scan_type = self.combo_scan_type.currentText()
        self._show_toast(f"{scan_type} 요소 스캔 중...", "info", 2000)
        QApplication.processEvents()
        
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
                self._show_toast(f"{len(elements)}개의 {scan_type} 요소를 찾았습니다.", "success")
            
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
            suggested_name = f"{element.tag}_{self.table.rowCount() + 1}"
        
        self.input_name.setText(suggested_name)
        self.input_desc.setText(element.text[:50] if element.text else "")
        
        self._show_toast(f"'{suggested_name}' 요소를 로드했습니다.", "success")
        
        # Playwright에서 하이라이트
        if self.pw_manager and self.pw_manager.is_alive():
            self.pw_manager.highlight(element.xpath, 2000)

    # =========================================================================
    # v4.0 신규 기능: Undo/Redo
    # =========================================================================
    
    def _update_undo_redo_actions(self):
        """Undo/Redo 액션 상태 업데이트"""
        self.undo_action.setEnabled(self.history_manager.can_undo())
        self.redo_action.setEnabled(self.history_manager.can_redo())
        
        if self.history_manager.can_undo():
            self.undo_action.setText(f"↩️ 실행 취소 ({self.history_manager.get_undo_description()})")
        else:
            self.undo_action.setText("↩️ 실행 취소")
    
    def _undo(self):
        """실행 취소"""
        restored = self.history_manager.undo()
        if restored:
            self._restore_items_from_dicts(restored)
            self._filter_options_dirty = True
            self._refresh_table(refresh_filters=True)
            self._update_undo_redo_actions()
            self._show_toast("실행 취소됨", "info")
    
    def _redo(self):
        """다시 실행"""
        restored = self.history_manager.redo()
        if restored:
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

    # =========================================================================
    # v4.0 신규 기능: 실시간 미리보기
    # =========================================================================
    
    def _on_xpath_text_changed(self):
        """XPath 입력 변경 시 실시간 미리보기 타이머 시작"""
        self._live_preview_timer.start()
    
    def _update_live_preview(self):
        """실시간 매칭 요소 수 업데이트 (비동기)"""
        with perf_span("ui.update_live_preview"):
            xpath = self.input_xpath.toPlainText().strip()
        
            if not xpath:
                self.lbl_live_preview.setText("🔍 매칭: -")
                self.lbl_live_preview.setStyleSheet("color: #6c7086; font-size: 11px;")
                return
            
            if not self.browser.is_alive():
                self.lbl_live_preview.setText("🔍 매칭: (브라우저 없음)")
                self.lbl_live_preview.setStyleSheet("color: #6c7086; font-size: 11px;")
                return

            self._live_preview_request_id += 1
            request_id = self._live_preview_request_id

            if self.live_preview_worker and self.live_preview_worker.isRunning():
                self.live_preview_worker.cancel()

            self.lbl_live_preview.setText("🔍 매칭: 계산 중...")
            self.lbl_live_preview.setStyleSheet("color: #89b4fa; font-size: 11px;")

            worker = LivePreviewWorker(self.browser, xpath, request_id)
            worker.counted.connect(self._on_live_preview_counted)
            worker.failed.connect(self._on_live_preview_failed)
            worker.finished.connect(lambda w=worker: self._on_live_preview_worker_finished(w))
            self.live_preview_worker = worker
            worker.start()

    def _on_live_preview_counted(self, request_id: int, count: int):
        if request_id != self._live_preview_request_id:
            return

        if count < 0:
            self.lbl_live_preview.setText("⚠️ 오류")
            self.lbl_live_preview.setStyleSheet("color: #f38ba8; font-size: 11px;")
        elif count == 0:
            self.lbl_live_preview.setText("❌ 매칭: 0개")
            self.lbl_live_preview.setStyleSheet("color: #f38ba8; font-size: 11px;")
        elif count == 1:
            self.lbl_live_preview.setText("✅ 매칭: 1개")
            self.lbl_live_preview.setStyleSheet("color: #a6e3a1; font-size: 11px;")
        else:
            self.lbl_live_preview.setText(f"🔍 매칭: {count}개")
            self.lbl_live_preview.setStyleSheet("color: #fab387; font-size: 11px;")

    def _on_live_preview_failed(self, request_id: int, _error: str):
        if request_id != self._live_preview_request_id:
            return
        self.lbl_live_preview.setText("⚠️ 오류")
        self.lbl_live_preview.setStyleSheet("color: #f38ba8; font-size: 11px;")

    def _on_live_preview_worker_finished(self, worker):
        if self.live_preview_worker is worker:
            self.live_preview_worker = None

    # =========================================================================
    # v4.0 신규 기능: XPath 대안 제안
    # =========================================================================
    
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
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        table.setColumnWidth(0, 50)
        table.setColumnWidth(1, 100)
        table.setColumnWidth(3, 60)
        table.verticalHeader().setVisible(False)
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

    # =========================================================================
    # v4.0 신규 기능: AI 어시스턴트
    # =========================================================================
    
    def _show_ai_assistant(self):
        """AI XPath 추천 다이얼로그"""
        dialog = QDialog(self)
        dialog.setWindowTitle("🤖 AI XPath 추천")
        dialog.resize(600, 450)
        
        layout = QVBoxLayout(dialog)
        
        # API 상태
        if self.ai_assistant.is_available():
            provider = self.ai_assistant._provider.capitalize()
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
            self.input_xpath.setPlainText(self._ai_result_text.toPlainText().split('\n')[1] if self._ai_result_text.toPlainText() else ""),
            self._show_toast("XPath 적용됨", "success")
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
        layout.addWidget(QLabel("AI Provider:"))
        combo_provider = QComboBox()
        combo_provider.addItems(["openai", "gemini"])
        combo_provider.setCurrentText(self.ai_assistant._provider)
        layout.addWidget(combo_provider)
        
        # API Key 입력
        layout.addWidget(QLabel("API Key:"))
        input_key = QLineEdit()
        input_key.setEchoMode(QLineEdit.EchoMode.Password)
        if self.ai_assistant._provider == "openai":
            input_key.setText(self.ai_assistant._config.get('openai_api_key', ''))
        else:
            input_key.setText(self.ai_assistant._config.get('gemini_api_key', ''))
        layout.addWidget(input_key)
        
        # Model 입력
        layout.addWidget(QLabel("Model:"))
        input_model = QLineEdit()
        input_model.setText(self.ai_assistant._model)
        layout.addWidget(input_model)
        
        # 힌트
        lbl_hint = QLabel("OpenAI: gpt-4o-mini, gpt-4o\nGemini: gemini-flash-latest, gemini-pro")
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

    # =========================================================================
    # v4.0 신규 기능: Diff 분석
    # =========================================================================
    
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
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        table.setColumnWidth(0, 50)
        table.setColumnWidth(1, 120)
        table.setColumnWidth(3, 200)
        table.verticalHeader().setVisible(False)
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

    # =========================================================================
    # v4.0 신규 기능: 스크린샷
    # =========================================================================
    
    def _screenshot_current_element(self):
        """현재 선택된 요소 스크린샷 저장"""
        xpath = self.input_xpath.toPlainText().strip()
        
        if not xpath:
            self._show_toast("XPath를 먼저 입력하세요.", "warning")
            return
        
        if not self.browser.is_alive():
            self._show_toast("브라우저를 먼저 연결하세요.", "warning")
            return
        
        # 저장 경로 선택
        fname, _ = QFileDialog.getSaveFileName(
            self, "스크린샷 저장", "element_screenshot.png", "PNG (*.png)"
        )
        
        if not fname:
            return
        
        # 스크린샷 저장
        success = self.browser.screenshot_element(xpath, fname)
        
        if success:
            self._show_toast(f"스크린샷 저장 완료: {fname}", "success")
            
            # 현재 항목에 스크린샷 경로 저장
            name = self.input_name.text().strip()
            item = self.config.get_item(name)
            if item:
                item.screenshot_path = fname
        else:
            self._show_toast("스크린샷 저장 실패", "error")

    def keyPressEvent(self, event):
        """키보드 이벤트 처리 - ESC로 배치 테스트 취소"""
        from PyQt6.QtCore import Qt
        if event.key() == Qt.Key.Key_Escape:
            if self.batch_worker and self.batch_worker.isRunning():
                self.batch_worker.cancel()
        super().keyPressEvent(event)

    def _save_settings(self):
        """설정 저장 (추가 설정용 확장 포인트)"""
        # 현재는 geometry만 별도 저장, 필요시 확장
        pass

    def closeEvent(self, event):
        """종료 처리"""
        logger.info("앱 종료 시작...")
        
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
            self.stats_manager.save()
            
        self.browser.close()
        logger.info("앱 종료 완료")
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
