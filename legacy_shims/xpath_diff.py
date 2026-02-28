# -*- coding: utf-8 -*-
"""Backward-compatible module shim.

Prefer importing from xpath_explorer.analysis.diff.
"""

import importlib
import sys

_impl = importlib.import_module('xpath_explorer.analysis.diff')
sys.modules[__name__] = _impl

