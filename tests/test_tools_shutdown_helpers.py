from xpath_explorer.core.config import SiteConfig
from xpath_explorer.core.constants import SITE_PRESETS, WORKER_WAIT_TIMEOUT
from xpath_explorer.mixins.data_mixin import ExplorerDataMixin
from xpath_explorer.mixins.tools_mixin import ExplorerToolsMixin


class _FakeSettings:
    def __init__(self, initial=None):
        self.data = dict(initial or {})

    def setValue(self, key, value):
        self.data[key] = value

    def value(self, key, default=None):
        return self.data.get(key, default)


class _FakeTabs:
    def __init__(self, index=0, count=2):
        self._index = index
        self._count = count

    def currentIndex(self):
        return self._index

    def setCurrentIndex(self, value):
        self._index = int(value)

    def count(self):
        return self._count


class _FakeToggleButton:
    def __init__(self):
        self.checked = True

    def setChecked(self, value):
        self.checked = bool(value)


class _FakeCollapsible:
    def __init__(self, expanded=True):
        self._expanded = expanded
        self.toggle_button = _FakeToggleButton()
        self.toggled_values = []

    def toggle(self, value):
        self._expanded = bool(value)
        self.toggled_values.append(bool(value))


class _FakePreset:
    def __init__(self, text):
        self._text = text
        self.blocked_values = []

    def currentText(self):
        return self._text

    def setCurrentText(self, text):
        self._text = text

    def blockSignals(self, blocked):
        self.blocked_values.append(bool(blocked))


class _FakeInput:
    def __init__(self):
        self.text = ""

    def setText(self, text):
        self.text = text


class _CancelWorker:
    def __init__(self, running=True, wait_ok=True):
        self._running = running
        self.wait_ok = wait_ok
        self.cancel_called = 0
        self.wait_args = []

    def isRunning(self):
        return self._running

    def cancel(self):
        self.cancel_called += 1

    def wait(self, timeout):
        self.wait_args.append(timeout)
        return self.wait_ok


class _StopWorker:
    def __init__(self):
        self.stop_called = 0
        self.wait_args = []

    def isRunning(self):
        return True

    def stop(self):
        self.stop_called += 1

    def wait(self, timeout):
        self.wait_args.append(timeout)
        return True


def _first_preset_name() -> str:
    return list(SITE_PRESETS.keys())[0]


class _ToolHost(ExplorerToolsMixin):
    def __init__(self):
        self.settings = _FakeSettings()
        self._font_size = 19
        self.right_tabs = _FakeTabs(index=1, count=3)
        self.url_collapsible = _FakeCollapsible(expanded=False)
        self.combo_preset = _FakePreset(_first_preset_name())


class _DataHost(ExplorerDataMixin):
    def __init__(self, settings):
        self.settings = settings
        self._font_size = 14
        self.config = SiteConfig.from_preset(_first_preset_name())
        self.combo_preset = _FakePreset(self.config.name)
        self.input_url = _FakeInput()
        self.right_tabs = _FakeTabs(index=0, count=3)
        self.url_collapsible = _FakeCollapsible(expanded=True)
        self._table_data_dirty = False
        self._filter_options_dirty = False
        self.restored_geometry = None
        self.applied_fonts = []

    def restoreGeometry(self, geometry):
        self.restored_geometry = geometry

    def _apply_font_size(self, size, notify=True):
        self._font_size = size
        self.applied_fonts.append((size, notify))


def test_tools_mixin_save_settings_persists_selected_keys():
    host = _ToolHost()
    host._save_settings()

    assert host.settings.data["ui/font_size"] == 19
    assert host.settings.data["ui/right_tab_index"] == 1
    assert host.settings.data["ui/url_panel_expanded"] is False
    assert host.settings.data["ui/last_preset"] == _first_preset_name()


def test_tools_mixin_stop_worker_thread_supports_cancel_and_stop_paths():
    host = _ToolHost()

    cancel_worker = _CancelWorker(running=True, wait_ok=True)
    host._stop_worker_thread(cancel_worker, "cancel-worker")
    assert cancel_worker.cancel_called == 1
    assert cancel_worker.wait_args == [WORKER_WAIT_TIMEOUT]

    stop_worker = _StopWorker()
    host._stop_worker_thread(stop_worker, "stop-worker")
    assert stop_worker.stop_called == 1
    assert stop_worker.wait_args == [WORKER_WAIT_TIMEOUT]


def test_data_mixin_load_settings_restores_font_preset_tab_and_url_panel():
    preset_names = list(SITE_PRESETS.keys())
    selected_preset = preset_names[-1]

    settings = _FakeSettings(
        {
            "geometry": b"fake-geometry",
            "ui/font_size": 17,
            "ui/right_tab_index": 2,
            "ui/url_panel_expanded": False,
            "ui/last_preset": selected_preset,
        }
    )
    host = _DataHost(settings)
    host._load_settings()

    assert host.restored_geometry == b"fake-geometry"
    assert host.applied_fonts[-1] == (17, False)
    assert host.right_tabs.currentIndex() == 2
    assert host.url_collapsible._expanded is False
    assert host.combo_preset.currentText() == selected_preset


def test_tools_mixin_classify_scenario_result_thresholds():
    host = _ToolHost()

    assert host._classify_scenario_result(5, 5, False) == ("success", "완료")
    assert host._classify_scenario_result(8, 10, False) == ("warning", "완료(일부 경고)")
    assert host._classify_scenario_result(7, 10, False) == ("error", "완료(실패 다수)")
    assert host._classify_scenario_result(0, 0, False) == ("warning", "완료(실행 결과 없음)")
    assert host._classify_scenario_result(1, 10, True) == ("warning", "취소됨")
