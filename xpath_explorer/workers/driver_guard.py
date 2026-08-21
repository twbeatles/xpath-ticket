# -*- coding: utf-8 -*-
"""Exclusive WebDriver occupancy helpers."""

from __future__ import annotations

from typing import Any, Tuple

EXCLUSIVE_WORKER_ATTRS = (
    "picker_watcher",
    "validate_worker",
    "batch_worker",
    "scenario_worker",
)


def exclusive_driver_worker_running(host: Any) -> Tuple[bool, str]:
    for name in EXCLUSIVE_WORKER_ATTRS:
        worker = getattr(host, name, None)
        if worker is None:
            continue
        is_running = getattr(worker, "isRunning", None)
        try:
            if callable(is_running) and bool(is_running()):
                return True, name
        except Exception:
            continue
    return False, ""
