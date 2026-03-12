from typing import Any, Callable, Dict, List, Optional, Tuple

from xpath_explorer.mixins import tools_mixin
from xpath_explorer.mixins.tools_mixin import ExplorerToolsMixin


class _Label:
    def __init__(self):
        self.text = ""
        self.style = ""

    def setText(self, text):
        self.text = str(text)

    def setStyleSheet(self, style):
        self.style = str(style)


class _Button:
    def __init__(self):
        self.text = ""
        self.enabled = True

    def setText(self, text):
        self.text = str(text)

    def setEnabled(self, value):
        self.enabled = bool(value)


class _LineEdit:
    def __init__(self, value):
        self._value = value

    def text(self):
        return self._value


class _Signal:
    def __init__(self):
        self._handlers: List[Callable[..., Any]] = []

    def connect(self, fn):
        self._handlers.append(fn)

    def emit(self, *args, **kwargs):
        for fn in list(self._handlers):
            fn(*args, **kwargs)


class _InstallWorker:
    next_result: Tuple[bool, str] = (True, "")

    def __init__(self):
        self.completed = _Signal()
        self._running = False
        self.start_called = 0

    def isRunning(self):
        return self._running

    def start(self):
        self._running = True
        self.start_called += 1
        ok, message = self.next_result
        self.completed.emit(ok, message)
        self._running = False


class _AlreadyRunningWorker:
    def isRunning(self):
        return True


class _PwManager:
    def __init__(
        self,
        launch_ok: bool = True,
        navigate_result: Optional[bool] = True,
        alive: bool = False,
        last_error: str = "",
    ):
        self.launch_ok = launch_ok
        self.navigate_result = navigate_result
        self._alive = alive
        self.last_error = last_error
        self.launch_calls = 0
        self.navigate_calls: List[str] = []
        self.close_calls = 0

    def launch(self, headless=False, stealth=True):
        _ = (headless, stealth)
        self.launch_calls += 1
        if self.launch_ok:
            self._alive = True
        return self.launch_ok

    def navigate(self, url):
        self.navigate_calls.append(url)
        return self.navigate_result

    def is_alive(self):
        return self._alive

    def close(self):
        self.close_calls += 1
        self._alive = False


class _Host(ExplorerToolsMixin):
    def __init__(self, manager, url="https://example.com"):
        self.pw_manager = manager
        self.input_url = _LineEdit(url)
        self.lbl_pw_status = _Label()
        self.btn_pw_toggle = _Button()
        self.playwright_install_worker: Any = None
        self.toasts = []

    def _show_toast(self, message, toast_type="info", duration=3000):
        self.toasts.append((str(message), str(toast_type), int(duration)))


def test_start_playwright_with_navigation_true_sets_success_status():
    host = _Host(_PwManager(launch_ok=True, navigate_result=True))

    ok = host._start_playwright_with_navigation("https://example.com")

    assert ok is True
    assert host.lbl_pw_status.text == "● 연결됨"
    assert host.btn_pw_toggle.text == "Playwright 종료"
    assert host.toasts[-1][1] == "success"


def test_start_playwright_with_navigation_timeout_shows_warning():
    host = _Host(_PwManager(launch_ok=True, navigate_result=None))

    ok = host._start_playwright_with_navigation("https://example.com")

    assert ok is True
    assert host.lbl_pw_status.text == "● 연결됨"
    assert host.toasts[-1][1] == "warning"


def test_start_playwright_with_navigation_failure_shows_warning():
    host = _Host(_PwManager(launch_ok=True, navigate_result=False))

    ok = host._start_playwright_with_navigation("https://example.com")

    assert ok is True
    assert host.lbl_pw_status.text == "● 연결됨"
    assert host.toasts[-1][1] == "warning"


def test_start_playwright_about_blank_skips_navigate():
    manager = _PwManager(launch_ok=True, navigate_result=False)
    host = _Host(manager, url="about:blank")

    ok = host._start_playwright_with_navigation("about:blank")

    assert ok is True
    assert manager.navigate_calls == []
    assert host.toasts[-1][1] == "success"


def test_toggle_playwright_launch_failure_triggers_install(monkeypatch):
    manager = _PwManager(launch_ok=False, navigate_result=False, alive=False, last_error="missing chromium")
    host = _Host(manager, url="https://tickets.example.com")
    captured: Dict[str, Optional[str]] = {"url": None}

    def remember_url(url: str):
        captured["url"] = url

    monkeypatch.setattr(
        "xpath_explorer.mixins.tools_mixin.QMessageBox.question",
        lambda *_args, **_kwargs: tools_mixin.QMessageBox.StandardButton.Yes,
    )
    host._begin_playwright_chromium_install = remember_url

    host._toggle_playwright()

    assert captured["url"] == "https://tickets.example.com"


def test_begin_playwright_chromium_install_skips_when_worker_running():
    host = _Host(_PwManager())
    host.playwright_install_worker = _AlreadyRunningWorker()

    host._begin_playwright_chromium_install("https://example.com")

    assert host.toasts[-1][1] == "info"


def test_on_playwright_chromium_installed_success_retries_start():
    host = _Host(_PwManager())
    called: Dict[str, Optional[str]] = {"url": None}
    host.btn_pw_toggle.setEnabled(False)
    host.playwright_install_worker = object()

    def fake_start(url: str) -> bool:
        called["url"] = url
        return True

    host._start_playwright_with_navigation = fake_start

    host._on_playwright_chromium_installed(True, "", "https://retry.example.com")

    assert called["url"] == "https://retry.example.com"
    assert host.playwright_install_worker is None
    assert host.btn_pw_toggle.enabled is True
    assert host.toasts[-1][1] == "success"


def test_on_playwright_chromium_installed_failure_sets_disconnected():
    host = _Host(_PwManager())
    host._set_playwright_status_ui(True)
    host.btn_pw_toggle.setEnabled(False)
    host.playwright_install_worker = object()

    host._on_playwright_chromium_installed(False, "boom", "https://retry.example.com")

    assert host.playwright_install_worker is None
    assert host.btn_pw_toggle.enabled is True
    assert host.lbl_pw_status.text == "● 미연결"
    assert host.toasts[-1][1] == "error"


def test_begin_playwright_chromium_install_runs_worker(monkeypatch):
    host = _Host(_PwManager())
    _InstallWorker.next_result = (False, "x")
    monkeypatch.setattr("xpath_explorer.mixins.tools_mixin.InstallChromiumWorker", _InstallWorker)

    host._begin_playwright_chromium_install("https://example.com")

    assert host.btn_pw_toggle.enabled is True
    # One immediate info toast and one completion toast(error) are expected.
    assert host.toasts[0][1] == "info"
    assert host.toasts[-1][1] == "error"
