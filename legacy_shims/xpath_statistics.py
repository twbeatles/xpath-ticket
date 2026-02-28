# -*- coding: utf-8 -*-
"""Backward-compatible module shim.

Prefer importing from xpath_explorer.analysis.statistics.
"""

import importlib
import sys

_impl = importlib.import_module('xpath_explorer.analysis.statistics')
sys.modules[__name__] = _impl

