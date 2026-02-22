# -*- coding: utf-8 -*-
"""XPath Explorer main window composition."""

import os
import sys
from typing import Optional

from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtCore import QTimer, QSettings
from PyQt6.QtGui import QAction

from xpath_constants import SEARCH_DEBOUNCE_MS, LIVE_PREVIEW_DEBOUNCE_MS
from xpath_config import SiteConfig
from xpath_browser import BrowserManager
from xpath_codegen import CodeGenerator
from xpath_statistics import StatisticsManager
from xpath_optimizer import XPathOptimizer
from xpath_history import HistoryManager
from xpath_ai import XPathAIAssistant
from xpath_diff import XPathDiffAnalyzer
from xpath_table_model import XPathItemTableModel
from xpath_filter_proxy import XPathFilterProxyModel

from xpath_explorer.runtime import logger
from xpath_explorer.mixins.ui_mixin import ExplorerUIMixin
from xpath_explorer.mixins.browser_mixin import ExplorerBrowserMixin
from xpath_explorer.mixins.data_mixin import ExplorerDataMixin
from xpath_explorer.mixins.tools_mixin import ExplorerToolsMixin


class XPathExplorer(
    ExplorerToolsMixin,
    ExplorerDataMixin,
    ExplorerBrowserMixin,
    ExplorerUIMixin,
    QMainWindow,
):
    """XPath ??? ??"""

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
        self._ai_last_xpath = ""
        self.undo_action: Optional[QAction] = None
        self.redo_action: Optional[QAction] = None
        
        # 상태 변수
        self._font_size = 14
        self._search_text = ""
        self._filter_favorites_only = False  # v3.3: 즐겨찾기 필터
        self._filter_tag = ""  # v3.3: 태그 필터
        self._filter_options_dirty = True
        self._table_data_dirty = True
        self.table_model = XPathItemTableModel([])
        self.table_proxy = XPathFilterProxyModel()
        self.table_proxy.setSourceModel(self.table_model)
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
        self._reset_history_baseline()

    def init_settings(self):
        self.settings = QSettings("MyCompany", "XPathExplorer")

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # 고해상도 지원
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    
    window = XPathExplorer()
    window.show()
    
    sys.exit(app.exec())
