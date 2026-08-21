# -*- coding: utf-8 -*-
# pyright: reportIncompatibleMethodOverride=false
"""XPath Explorer application window composition."""

import os
import sys
from typing import TYPE_CHECKING, Any, cast

from xpath_explorer.qt_compat import QT_AVAILABLE, require_qt

if TYPE_CHECKING:
    from PyQt6.QtCore import QSettings, QTimer
    from PyQt6.QtWidgets import QApplication, QMainWindow
    from xpath_explorer.analysis.diff import XPathDiffAnalyzer
    from xpath_explorer.analysis.statistics import StatisticsManager
    from xpath_explorer.browser.browser import BrowserManager
    from xpath_explorer.core.config import SiteConfig
    from xpath_explorer.core.constants import LIVE_PREVIEW_DEBOUNCE_MS, SEARCH_DEBOUNCE_MS
    from xpath_explorer.mixins.browser_mixin import ExplorerBrowserMixin
    from xpath_explorer.mixins.data_mixin import ExplorerDataMixin
    from xpath_explorer.mixins.tools_mixin import ExplorerToolsMixin
    from xpath_explorer.mixins.ui_mixin import ExplorerUIMixin
    from xpath_explorer.state.history import HistoryManager
    from xpath_explorer.tools.ai import XPathAIAssistant
    from xpath_explorer.tools.codegen import CodeGenerator
    from xpath_explorer.tools.optimizer import XPathOptimizer
    from xpath_explorer.ui.filter_proxy import XPathFilterProxyModel
    from xpath_explorer.ui.table_model import XPathItemTableModel
elif QT_AVAILABLE:
    from PyQt6.QtCore import QSettings, QTimer
    from PyQt6.QtWidgets import QApplication, QMainWindow
    from xpath_explorer.analysis.diff import XPathDiffAnalyzer
    from xpath_explorer.analysis.statistics import StatisticsManager
    from xpath_explorer.browser.browser import BrowserManager
    from xpath_explorer.core.config import SiteConfig
    from xpath_explorer.core.constants import LIVE_PREVIEW_DEBOUNCE_MS, SEARCH_DEBOUNCE_MS
    from xpath_explorer.mixins.browser_mixin import ExplorerBrowserMixin
    from xpath_explorer.mixins.data_mixin import ExplorerDataMixin
    from xpath_explorer.mixins.tools_mixin import ExplorerToolsMixin
    from xpath_explorer.mixins.ui_mixin import ExplorerUIMixin
    from xpath_explorer.state.history import HistoryManager
    from xpath_explorer.tools.ai import XPathAIAssistant
    from xpath_explorer.tools.codegen import CodeGenerator
    from xpath_explorer.tools.optimizer import XPathOptimizer
    from xpath_explorer.ui.filter_proxy import XPathFilterProxyModel
    from xpath_explorer.ui.table_model import XPathItemTableModel
else:
    from xpath_explorer.qt_compat import QApplication, QMainWindow, QSettings, QTimer


def configure_qt_env():
    """Configure Qt environment before QApplication initialization."""
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"


if QT_AVAILABLE:

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
            self.stats_manager = StatisticsManager()
            self.code_generator = CodeGenerator()
            self.pw_manager = None
            self.optimizer = XPathOptimizer()
            self.history_manager = HistoryManager()
            self.ai_assistant = XPathAIAssistant()
            self.diff_analyzer = XPathDiffAnalyzer()

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
            self._frame_selection_explicit = False
            self._window_selection_explicit = False
            self._dom_diff_baseline = []
            self._dom_diff_source = ""
            self._editing_original_name = ""
            self.undo_action = None
            self.redo_action = None

            self._font_size = 14
            self._search_text = ""
            self._filter_favorites_only = False
            self._filter_tag = ""
            self._filter_options_dirty = True
            self._table_data_dirty = True
            self.table_model = XPathItemTableModel([])
            self.table_proxy = XPathFilterProxyModel()
            self.table_proxy.setSourceModel(self.table_model)
            self._search_timer = QTimer()
            self._search_timer.setSingleShot(True)
            self._search_timer.setInterval(SEARCH_DEBOUNCE_MS)
            self._search_timer.timeout.connect(self._perform_search)
            self._live_preview_timer = QTimer()
            self._live_preview_timer.setSingleShot(True)
            self._live_preview_timer.setInterval(LIVE_PREVIEW_DEBOUNCE_MS)
            self._live_preview_timer.timeout.connect(self._update_live_preview)

            self.init_settings()
            self._init_ui()
            self._load_settings()
            self._setup_timers()
            self._refresh_table(refresh_filters=True)
            self._reset_history_baseline()
            self._mark_config_clean()

        def init_settings(self):
            from xpath_explorer.core.constants import (
                QSETTINGS_APP,
                QSETTINGS_LEGACY_APP,
                QSETTINGS_LEGACY_ORG,
                QSETTINGS_ORG,
            )

            self.settings = QSettings(QSETTINGS_ORG, QSETTINGS_APP)
            if not self.settings.contains("geometry"):
                legacy = QSettings(QSETTINGS_LEGACY_ORG, QSETTINGS_LEGACY_APP)
                for key in legacy.allKeys():
                    if not self.settings.contains(key):
                        self.settings.setValue(key, legacy.value(key))
else:

    class _HeadlessXPathExplorer:  # pragma: no cover - exercised only in headless CI
        def __init__(self, *_args, **_kwargs):
            require_qt()

    XPathExplorer = cast(Any, _HeadlessXPathExplorer)


def main():
    configure_qt_env()
    require_qt()
    if not QT_AVAILABLE:
        return
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = XPathExplorer()
    window.show()

    sys.exit(app.exec())
