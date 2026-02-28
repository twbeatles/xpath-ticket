# -*- coding: utf-8 -*-
"""Backward-compatible module shim.

Prefer importing from xpath_explorer.workers.background.
"""

import importlib
import sys

_impl = importlib.import_module('xpath_explorer.workers.background')
sys.modules[__name__] = _impl

