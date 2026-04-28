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


class ExplorerUIMenuMixin:
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
             ('JSON 파일 (*.json)', 'json'),
             ('CSV 파일 (*.csv)', 'csv'),
             ('파이썬 Selenium (*.py)', 'python'),
             ('자바스크립트 (*.js)', 'javascript')
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

        batch_scenario_action = QAction('시나리오 실행기...', self)
        batch_scenario_action.triggered.connect(self._show_batch_scenario_runner)
        batch_menu.addAction(batch_scenario_action)
        
        # v3.3 매크로 생성
        macro_action = QAction('🔧 매크로 생성...', self)
        macro_action.triggered.connect(self._show_macro_generator)
        tools_menu.addAction(macro_action)

        template_action = QAction('📚 XPath 템플릿 라이브러리...', self)
        template_action.triggered.connect(self._show_xpath_template_library)
        tools_menu.addAction(template_action)
        
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

        dom_diff_action = QAction('🧾 DOM 비교 리포트', self)
        dom_diff_action.triggered.connect(self._export_dom_diff_report)
        tools_menu.addAction(dom_diff_action)

        screenshot_action = QAction('📸 요소 스크린샷...', self)
        screenshot_action.triggered.connect(self._screenshot_current_element)
        tools_menu.addAction(screenshot_action)
        
        tools_menu.addSeparator()
        
        # v3.3 통계
        stats_action = QAction('📈 통계 보기', self)
        stats_action.triggered.connect(self._show_statistics)
        tools_menu.addAction(stats_action)

        validation_history_action = QAction('🕒 검증 히스토리 패널', self)
        validation_history_action.triggered.connect(self._show_validation_history_panel)
        tools_menu.addAction(validation_history_action)

        telemetry_action = QAction('🚨 오류 텔레메트리', self)
        telemetry_action.triggered.connect(self._show_error_telemetry)
        tools_menu.addAction(telemetry_action)

        diagnostics_action = QAction('🧭 기능 진단 리포트 저장...', self)
        diagnostics_action.triggered.connect(self._save_feature_diagnostics_report)
        tools_menu.addAction(diagnostics_action)
        
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
