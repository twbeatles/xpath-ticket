# -*- coding: utf-8 -*-
# pyright: reportArgumentType=false
"""Diff analysis entry guard (ISSUE-004) regression tests."""

from types import SimpleNamespace

from xpath_explorer.mixins.tools.inspection.diff_panel import DiffInspectionMixin
from xpath_explorer.mixins.tools.lifecycle_tools import ExplorerLifecycleToolsMixin


class _FakeBrowser:
    def __init__(self, alive):
        self._alive = alive

    def is_alive(self):
        return self._alive


class _RunningWorker:
    def isRunning(self):
        return True


def _host(alive, worker=None):
    toasts = []
    host = SimpleNamespace(
        browser=_FakeBrowser(alive),
        picker_watcher=None,
        validate_worker=worker,
        batch_worker=None,
        scenario_worker=None,
        _show_toast=lambda msg, _kind="info", *_a: toasts.append(msg),
    )
    host.toasts = toasts
    host._abort_if_driver_busy = (
        ExplorerLifecycleToolsMixin._abort_if_driver_busy.__get__(host)
    )
    return host


def test_diff_analyzer_requires_selenium_explicitly():
    host = _host(False)

    DiffInspectionMixin._show_diff_analyzer(host)

    assert len(host.toasts) == 1
    assert "Selenium" in host.toasts[0]


def test_diff_analyzer_refuses_while_driver_busy():
    host = _host(True, worker=_RunningWorker())

    DiffInspectionMixin._show_diff_analyzer(host)

    assert len(host.toasts) == 1
    assert "Diff 분석" in host.toasts[0]
