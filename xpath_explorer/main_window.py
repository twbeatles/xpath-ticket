# -*- coding: utf-8 -*-
# pyright: reportIncompatibleMethodOverride=false
"""XPath Explorer main window composition."""

import os
import sys
from typing import Optional

from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtCore import QTimer, QSettings
from PyQt6.QtGui import QAction

from xpath_explorer.core.constants import SEARCH_DEBOUNCE_MS, LIVE_PREVIEW_DEBOUNCE_MS
from xpath_explorer.core.config import SiteConfig
from xpath_explorer.browser.browser import BrowserManager
from xpath_explorer.tools.codegen import CodeGenerator
from xpath_explorer.analysis.statistics import StatisticsManager
from xpath_explorer.tools.optimizer import XPathOptimizer
from xpath_explorer.state.history import HistoryManager
from xpath_explorer.tools.ai import XPathAIAssistant
from xpath_explorer.analysis.diff import XPathDiffAnalyzer
from xpath_explorer.ui.table_model import XPathItemTableModel
from xpath_explorer.ui.filter_proxy import XPathFilterProxyModel

from xpath_explorer.runtime import logger
from xpath_explorer.mixins.ui_mixin import ExplorerUIMixin
from xpath_explorer.mixins.browser_mixin import ExplorerBrowserMixin
from xpath_explorer.mixins.data_mixin import ExplorerDataMixin
from xpath_explorer.mixins.tools_mixin import ExplorerToolsMixin


def configure_qt_env():
    """Configure Qt environment before QApplication initialization."""
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

class XPathExplorer(
    ExplorerToolsMixin,
    ExplorerDataMixin,
    ExplorerBrowserMixin,
    ExplorerUIMixin,
    QMainWindow,
):
    """XPath Explorer 메인 윈도우."""

    def __init__(self):
        super().__init__()
        
        self.browser = BrowserManager()
        self.config = SiteConfig.from_preset("인터파크")

        # v3.3: 통계 관리자 및 코드 생성기
        self.stats_manager = StatisticsManager()
        self.code_generator = CodeGenerator()

        # v3.4: Playwright 매니저 (지연 초기화)
        self.pw_manager = None

        # v4.0 도구 모듈
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
        self.scenario_worker = None
        self.playwright_install_worker = None
        self._live_preview_request_id = 0
        self._ai_request_id = 0
        self._ai_last_xpath = ""
        self._dom_diff_baseline = []
        self._dom_diff_source = ""
        self._editing_original_name = ""
        self.undo_action: Optional[QAction] = None
        self.redo_action: Optional[QAction] = None
        
        # UI 상태
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
        
        # v4.0: 히스토리 기준점 초기화
        self._reset_history_baseline()

    def init_settings(self):
        self.settings = QSettings("MyCompany", "XPathExplorer")

def main():
    configure_qt_env()
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    window = XPathExplorer()
    window.show()
    
    sys.exit(app.exec())
