# -*- coding: utf-8 -*-
"""Backward-compatible module shim.

Prefer importing from xpath_explorer.state.history.
"""

import importlib
import sys

_impl = importlib.import_module('xpath_explorer.state.history')
sys.modules[__name__] = _impl

