# -*- coding: utf-8 -*-
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
    """XPath ??? ??"""

    def __init__(self):
        super().__init__()
        
        self.browser = BrowserManager()
        self.config = SiteConfig.from_preset("?명꽣?뚰겕")
        
        # v3.3 ?좉퇋: ?듦퀎 愿由ъ옄 諛?肄붾뱶 ?앹꽦湲?
        self.stats_manager = StatisticsManager()
        self.code_generator = CodeGenerator()
        
        # v3.4 ?좉퇋: Playwright 留ㅻ땲? (?먮룞 ?붿냼 ?먯깋??
        self.pw_manager = None  # 吏??珥덇린??
        
        # v4.0 ?좉퇋 紐⑤뱢
        self.optimizer = XPathOptimizer()
        self.history_manager = HistoryManager()
        self.ai_assistant = XPathAIAssistant()
        self.diff_analyzer = XPathDiffAnalyzer()
        
        # ?뚯빱 ?ㅻ젅??愿由?
        self.picker_watcher = None
        self.validate_worker = None
        self.live_preview_worker = None
        self.ai_worker = None
        self.diff_worker = None
        self.batch_worker = None
        self.scenario_worker = None
        self._live_preview_request_id = 0
        self._ai_request_id = 0
        self._ai_last_xpath = ""
        self._dom_diff_baseline = []
        self._dom_diff_source = ""
        self.undo_action: Optional[QAction] = None
        self.redo_action: Optional[QAction] = None
        
        # ?곹깭 蹂??
        self._font_size = 14
        self._search_text = ""
        self._filter_favorites_only = False  # v3.3: 利먭꺼李얘린 ?꾪꽣
        self._filter_tag = ""  # v3.3: ?쒓렇 ?꾪꽣
        self._filter_options_dirty = True
        self._table_data_dirty = True
        self.table_model = XPathItemTableModel([])
        self.table_proxy = XPathFilterProxyModel()
        self.table_proxy.setSourceModel(self.table_model)
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(SEARCH_DEBOUNCE_MS)
        self._search_timer.timeout.connect(self._perform_search)
        
        # v4.0: ?ㅼ떆媛?誘몃━蹂닿린 ??대㉧
        self._live_preview_timer = QTimer()
        self._live_preview_timer.setSingleShot(True)
        self._live_preview_timer.setInterval(LIVE_PREVIEW_DEBOUNCE_MS)
        self._live_preview_timer.timeout.connect(self._update_live_preview)
        
        self.init_settings()
        self._init_ui()
        self._load_settings()
        self._setup_timers()
        self._refresh_table(refresh_filters=True)
        
        # v4.0: ?덉뒪?좊━ 珥덇린??
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
