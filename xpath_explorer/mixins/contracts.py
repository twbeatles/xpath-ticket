# -*- coding: utf-8 -*-
"""Typed host protocols shared by split mixins."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ExplorerHostProtocol(Protocol):
    config: Any
    browser: Any
    settings: Any

    def _show_toast(self, message: str, toast_type: str = "info", duration: int = 3000) -> None: ...
    def _refresh_table(self, filter_cat: str | None = None, refresh_filters: bool = False) -> Any: ...
    def _load_settings(self) -> None: ...


class ExplorerBrowserHostProtocol(ExplorerHostProtocol, Protocol):
    pw_manager: Any
    table_model: Any
    table_proxy: Any


class ExplorerDataHostProtocol(ExplorerHostProtocol, Protocol):
    history_manager: Any


class ExplorerToolsHostProtocol(ExplorerHostProtocol, Protocol):
    stats_manager: Any
    ai_assistant: Any


class ExplorerUIHostProtocol(ExplorerHostProtocol, Protocol):
    pass
