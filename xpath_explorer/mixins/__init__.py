"""Lazy exports for mixin classes."""

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from xpath_explorer.mixins.browser_mixin import ExplorerBrowserMixin
    from xpath_explorer.mixins.data_mixin import ExplorerDataMixin
    from xpath_explorer.mixins.tools_mixin import ExplorerToolsMixin
    from xpath_explorer.mixins.ui_mixin import ExplorerUIMixin

__all__ = [
    "ExplorerUIMixin",
    "ExplorerBrowserMixin",
    "ExplorerDataMixin",
    "ExplorerToolsMixin",
]

_MIXIN_MODULES = {
    "ExplorerUIMixin": "xpath_explorer.mixins.ui_mixin",
    "ExplorerBrowserMixin": "xpath_explorer.mixins.browser_mixin",
    "ExplorerDataMixin": "xpath_explorer.mixins.data_mixin",
    "ExplorerToolsMixin": "xpath_explorer.mixins.tools_mixin",
}


def __getattr__(name: str):
    module_name = _MIXIN_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(module_name)
    return getattr(module, name)
