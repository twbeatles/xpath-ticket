# -*- coding: utf-8 -*-
"""Backward-compatible module shim.

Prefer importing from xpath_explorer.ui.table_model.
"""

import importlib
import sys

_impl = importlib.import_module('xpath_explorer.ui.table_model')
sys.modules[__name__] = _impl

