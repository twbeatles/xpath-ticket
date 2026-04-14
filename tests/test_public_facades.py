from xpath_explorer.browser.browser import BrowserManager
from xpath_explorer.browser.playwright import NetworkAnalyzer, PlaywrightManager
from xpath_explorer.core.constants import APP_TITLE, PICKER_SCRIPT, SITE_PRESETS, WORKER_WAIT_TIMEOUT
from xpath_explorer.mixins.browser_mixin import ExplorerBrowserMixin
from xpath_explorer.mixins.data_mixin import ExplorerDataMixin
from xpath_explorer.mixins.tools_mixin import ExplorerToolsMixin
from xpath_explorer.mixins.ui_mixin import ExplorerUIMixin
from xpath_explorer.workers.background import (
    AIGenerateWorker,
    BatchScenarioWorker,
    BatchTestWorker,
    DiffAnalyzeWorker,
    InstallChromiumWorker,
    LivePreviewWorker,
    PickerWatcher,
    ValidateWorker,
)


def test_legacy_facade_imports_remain_available():
    assert ExplorerUIMixin is not None
    assert ExplorerBrowserMixin is not None
    assert ExplorerDataMixin is not None
    assert ExplorerToolsMixin is not None
    assert BrowserManager is not None
    assert PlaywrightManager is not None
    assert NetworkAnalyzer is not None


def test_constants_facade_reexports_representative_values():
    assert isinstance(APP_TITLE, str)
    assert APP_TITLE
    assert isinstance(PICKER_SCRIPT, str)
    assert "window.__pickerActive" in PICKER_SCRIPT
    assert isinstance(SITE_PRESETS, dict)
    assert SITE_PRESETS
    assert isinstance(WORKER_WAIT_TIMEOUT, int)
    assert WORKER_WAIT_TIMEOUT > 0


def test_workers_facade_reexports_worker_classes():
    for worker_class in (
        PickerWatcher,
        ValidateWorker,
        LivePreviewWorker,
        AIGenerateWorker,
        DiffAnalyzeWorker,
        BatchTestWorker,
        BatchScenarioWorker,
        InstallChromiumWorker,
    ):
        assert isinstance(worker_class.__name__, str)
        assert worker_class.__name__
