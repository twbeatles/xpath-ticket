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


class ExplorerUIBrowserPanelMixin:
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
        self.combo_frames.currentIndexChanged.connect(self._on_frame_changed)
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

        self.btn_export_dom = QToolButton()
        self.btn_export_dom.setText("DOM")
        self.btn_export_dom.setObjectName("icon_btn")
        self.btn_export_dom.setToolTip("DOM 저장 범위 선택")
        self.btn_export_dom.setFixedSize(56, 26)
        self.btn_export_dom.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        selenium_dom_menu = QMenu(self.btn_export_dom)
        selenium_dom_menu.addAction("전체 DOM 저장", lambda: self._export_dom_selenium_htm(scope="all", include_frames=True))
        selenium_dom_menu.addAction("현재 창 DOM 저장", lambda: self._export_dom_selenium_htm(scope="current", include_frames=False))
        selenium_dom_menu.addAction("현재 창 + iframe DOM 저장", lambda: self._export_dom_selenium_htm(scope="current", include_frames=True))
        self.btn_export_dom.setMenu(selenium_dom_menu)
        self.browser_layout.addWidget(self.btn_export_dom)
        
        # URL 입력창 (구버전 제거, 하단 Collapsible 영역으로 이동)
        self.browser_layout.addStretch()
