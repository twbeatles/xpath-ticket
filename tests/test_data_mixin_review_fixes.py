import json
from types import SimpleNamespace

from xpath_explorer.core.config import SiteConfig, XPathItem
from xpath_explorer.mixins.data_mixin import ExplorerDataMixin
from xpath_explorer.tools.codegen import CodeGenerator


class _LineEdit:
    def __init__(self, value: str = ""):
        self._value = value

    def text(self):
        return self._value

    def setText(self, value: str):
        self._value = value

    def clear(self):
        self._value = ""


class _PlainTextEdit:
    def __init__(self, value: str = ""):
        self._value = value

    def toPlainText(self):
        return self._value

    def setPlainText(self, value: str):
        self._value = value

    def clear(self):
        self._value = ""


class _ComboBox:
    def __init__(self, data: str = "common", text: str = "common"):
        self._data = data
        self._text = text

    def currentData(self):
        return self._data

    def currentText(self):
        return self._text

    def findData(self, data):
        return 0 if data == self._data else -1

    def setCurrentIndex(self, _index):
        pass

    def setCurrentText(self, text):
        self._text = text


class _HistoryManager:
    def __init__(self):
        self.push_calls = []
        self.sync_calls = 0

    def push_state(self, _items, action, action_name, action_desc):
        self.push_calls.append((action, action_name, action_desc))

    def sync_current_state(self, _items):
        self.sync_calls += 1


class _FakeSettings:
    def __init__(self, value):
        self._value = value

    def value(self, key, default=None):
        if key == "xpath_history":
            return self._value
        return default

    def setValue(self, key, value):
        if key == "xpath_history":
            self._value = value


class _CookieDriver:
    def __init__(self, failing_names=None, failing_domains=None):
        self._failing_names = set(failing_names or [])
        self._failing_domains = set(failing_domains or [])
        self.added = []
        self.refresh_called = 0

    def add_cookie(self, cookie):
        self.added.append(cookie)
        name = str(cookie.get("name", "") or "")
        domain = str(cookie.get("domain", "") or "")
        if name in self._failing_names or domain in self._failing_domains:
            raise RuntimeError("cookie rejected")

    def refresh(self):
        self.refresh_called += 1


class _DataHost(ExplorerDataMixin):
    def __init__(self, items):
        self.config = SiteConfig(name="test", url="https://example.com", items=list(items))
        self.history_manager = _HistoryManager()
        self.browser = SimpleNamespace(current_frame_path="", is_alive=lambda: True, driver=None)
        self.code_generator = CodeGenerator()
        self.input_name = _LineEdit()
        self.input_xpath = _PlainTextEdit()
        self.input_desc = _LineEdit()
        self.input_css = _LineEdit()
        self.input_tags = _LineEdit()
        self.input_category = _ComboBox()
        self.txt_result = _PlainTextEdit()
        self.settings = _FakeSettings([])
        self._editing_original_name = ""
        self._table_data_dirty = False
        self._filter_options_dirty = False
        self.refresh_calls = 0
        self.undo_calls = 0
        self.toasts = []

    def _refresh_table(self, refresh_filters=False):
        _ = refresh_filters
        self.refresh_calls += 1

    def _update_undo_redo_actions(self):
        self.undo_calls += 1

    def _show_toast(self, message, toast_type="info", duration=3000):
        self.toasts.append((str(message), str(toast_type), int(duration)))


def _item(name: str, xpath: str) -> XPathItem:
    return XPathItem(name=name, xpath=xpath, category="common", description=f"desc-{name}")


def test_save_item_blocks_rename_conflict():
    host = _DataHost([_item("alpha", "//a"), _item("beta", "//b")])
    host._editing_original_name = "alpha"
    host.input_name.setText("beta")
    host.input_xpath.setPlainText("//updated")

    host._save_item()

    assert host.config.get_item("alpha") is not None
    beta_item = host.config.get_item("beta")
    assert beta_item is not None
    assert beta_item.xpath == "//b"
    assert host.history_manager.push_calls == []
    assert any(toast_type == "warning" for _, toast_type, _ in host.toasts)


def test_save_item_rename_keeps_metadata_and_updates_original_name():
    source = _item("alpha", "//a")
    source.is_favorite = True
    source.test_count = 4
    source.success_count = 3
    source.found_frame = "frame1"
    source.found_window = "old-popup"
    source.found_window_title = "Old Popup"
    source.found_window_url = "https://old-popup.example"
    host = _DataHost([source])
    host._editing_original_name = "alpha"
    host.input_name.setText("alpha_renamed")
    host.input_xpath.setPlainText("//renamed")
    host.browser.current_frame_path = "frame2"
    host.browser = SimpleNamespace(
        current_frame_path="frame2",
        is_alive=lambda: True,
        driver=None,
        get_current_window_metadata=lambda: {
            "handle": "new-popup",
            "title": "New Popup",
            "url": "https://new-popup.example",
        },
    )

    host._save_item()

    renamed = host.config.get_item("alpha_renamed")
    assert renamed is not None
    assert host.config.get_item("alpha") is None
    assert renamed.is_favorite is True
    assert renamed.test_count == 4
    assert renamed.success_count == 3
    assert renamed.found_frame == "frame2"
    assert renamed.found_window == "new-popup"
    assert renamed.found_window_title == "New Popup"
    assert renamed.found_window_url == "https://new-popup.example"
    assert host._editing_original_name == "alpha_renamed"
    assert host.history_manager.push_calls[0][0] == "rename"


def test_save_item_uses_playwright_source_context_without_stale_selenium_frame():
    host = _DataHost([])
    host.input_name.setText("from_scan")
    host.input_xpath.setPlainText("//button")
    host.browser = SimpleNamespace(
        current_frame_path="stale_selenium_frame",
        is_alive=lambda: True,
        driver=None,
        get_current_window_metadata=lambda: {
            "handle": "selenium-window",
            "title": "Selenium",
            "url": "https://selenium.example",
        },
    )
    host._editing_source_engine = "playwright"
    host._editing_source_frame = "pw-frame"
    host._editing_source_window = "pw-page-2"
    host._editing_source_window_title = "Playwright Popup"
    host._editing_source_window_url = "https://popup.example"

    host._save_item()

    item = host.config.get_item("from_scan")
    assert item is not None
    assert item.found_frame == "pw-frame"
    assert item.found_window == "pw-page-2"
    assert item.found_window_title == "Playwright Popup"
    assert item.found_window_url == "https://popup.example"


def test_export_python_uses_safe_names_and_suffixes(tmp_path, monkeypatch):
    host = _DataHost(
        [
            _item("dup name", "//x1"),
            _item("dup-name", "//x2"),
            _item("1login", "//x3"),
        ]
    )
    target = tmp_path / "export.py"

    monkeypatch.setattr(
        "xpath_explorer.mixins.data_mixin.QFileDialog.getSaveFileName",
        lambda *_args, **_kwargs: (str(target), ""),
    )

    host._export("python")

    content = target.read_text(encoding="utf-8")
    compile(content, "<test-export>", "exec")
    scope = {}
    exec(content, scope)
    attrs = [name for name in vars(scope["XPaths"]) if not name.startswith("__")]

    assert "DUP_NAME" in attrs
    assert "DUP_NAME_2" in attrs
    assert "_1LOGIN" in attrs
    assert len(attrs) == 3
    assert any(toast_type == "success" for _, toast_type, _ in host.toasts)


def test_export_python_compile_failure_aborts_write(tmp_path, monkeypatch):
    host = _DataHost([_item("alpha", "//x")])
    target = tmp_path / "export_fail.py"

    monkeypatch.setattr(
        "xpath_explorer.mixins.data_mixin.QFileDialog.getSaveFileName",
        lambda *_args, **_kwargs: (str(target), ""),
    )
    monkeypatch.setattr("builtins.compile", lambda *_args, **_kwargs: (_ for _ in ()).throw(SyntaxError("boom")))

    host._export("python")

    assert not target.exists()
    assert any(toast_type == "error" for _, toast_type, _ in host.toasts)


def test_load_xpath_history_data_normalizes_types():
    host = _DataHost([])
    host.settings = _FakeSettings(["bad", {"xpath": "//a"}, 3, {"xpath": "//b"}])

    history = host._load_xpath_history_data()

    assert history == [{"xpath": "//a"}, {"xpath": "//b"}]


def test_load_xpath_history_data_handles_non_list():
    host = _DataHost([])
    host.settings = _FakeSettings({"xpath": "//a"})

    assert host._load_xpath_history_data() == []


def test_load_cookies_reports_success_and_failures(tmp_path, monkeypatch):
    host = _DataHost([])
    driver = _CookieDriver(failing_names={"bad"}, failing_domains={"example.com"})
    host.browser = SimpleNamespace(current_frame_path="", is_alive=lambda: True, driver=driver)

    cookie_path = tmp_path / "cookies.json"
    cookie_path.write_text(
        json.dumps(
            [
                {"name": "ok", "value": "1"},
                {"name": "bad", "value": "2"},
                {"domain": "example.com", "value": "3"},
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "xpath_explorer.mixins.data_mixin.QFileDialog.getOpenFileName",
        lambda *_args, **_kwargs: (str(cookie_path), ""),
    )

    host._load_cookies()

    assert len(driver.added) == 3
    assert driver.refresh_called == 1
    message, toast_type, _ = host.toasts[-1]
    assert toast_type == "warning"
    assert "1" in message
    assert "2" in message
    assert "bad(1)" in message
    assert "example.com(1)" in message


def test_load_cookies_rejects_non_list_payload(tmp_path, monkeypatch):
    host = _DataHost([])
    driver = _CookieDriver()
    host.browser = SimpleNamespace(current_frame_path="", is_alive=lambda: True, driver=driver)

    cookie_path = tmp_path / "bad_cookies.json"
    cookie_path.write_text(json.dumps({"name": "not-list"}), encoding="utf-8")
    monkeypatch.setattr(
        "xpath_explorer.mixins.data_mixin.QFileDialog.getOpenFileName",
        lambda *_args, **_kwargs: (str(cookie_path), ""),
    )

    host._load_cookies()

    assert driver.refresh_called == 0
    assert host.toasts[-1][1] == "error"
