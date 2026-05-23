import sys

import xpath_explorer.browser.playwright_lifecycle as lifecycle
from xpath_explorer.workers.install_worker import InstallChromiumWorker


class _CancelEvent:
    def __init__(self, value=False):
        self._value = value

    def is_set(self):
        return self._value


def test_install_chromium_uses_bundled_main_when_frozen_without_cli(monkeypatch):
    calls = []

    monkeypatch.setattr(lifecycle.shutil, "which", lambda _name: None)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(
        lifecycle.PlaywrightLifecycleMixin,
        "_run_playwright_subprocess",
        lambda cmd, **kwargs: calls.append(list(cmd)) or False,
    )
    monkeypatch.setattr(
        lifecycle.PlaywrightLifecycleMixin,
        "_run_playwright_main_install",
        lambda: True,
    )

    assert lifecycle.PlaywrightLifecycleMixin.install_chromium() is True
    assert calls == []


def test_install_chromium_uses_current_python_module_when_not_frozen(monkeypatch):
    calls = []

    monkeypatch.setattr(lifecycle.shutil, "which", lambda _name: None)
    monkeypatch.setattr(sys, "frozen", False, raising=False)

    def fake_subprocess(cmd, **_kwargs):
        calls.append(list(cmd))
        return True

    monkeypatch.setattr(lifecycle.PlaywrightLifecycleMixin, "_run_playwright_subprocess", fake_subprocess)
    monkeypatch.setattr(lifecycle.PlaywrightLifecycleMixin, "_run_playwright_main_install", lambda: False)

    assert lifecycle.PlaywrightLifecycleMixin.install_chromium() is True
    assert calls == [[sys.executable, "-m", "playwright", "install", "chromium"]]


def test_install_worker_passes_cancel_event_to_installer():
    captured = {}

    def installer(cancel_event):
        captured["cancel_event"] = cancel_event
        return True

    worker = InstallChromiumWorker(installer=installer)
    worker.run()

    assert captured["cancel_event"].is_set() is False
