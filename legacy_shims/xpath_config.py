# -*- coding: utf-8 -*-
"""Backward-compatible module shim.

Prefer importing from xpath_explorer.core.config.
"""

import importlib
import sys

_impl = importlib.import_module('xpath_explorer.core.config')
sys.modules[__name__] = _impl

