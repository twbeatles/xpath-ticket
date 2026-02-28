# -*- coding: utf-8 -*-
"""Backward-compatible module shim.

Prefer importing from xpath_explorer.ui.styles.
"""

import importlib
import sys

_impl = importlib.import_module('xpath_explorer.ui.styles')
sys.modules[__name__] = _impl

