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


class ExplorerUIListPanelMixin:
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
        self.combo_filter.addItem("전체", "")
        self.combo_filter.setMinimumWidth(90)
        self.combo_filter.currentIndexChanged.connect(lambda _=None: self._refresh_table())
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
