# -*- coding: utf-8 -*-
"""Backward-compatible module shim.

Prefer importing from xpath_explorer.core.constants.
"""

import importlib
import sys

_impl = importlib.import_module('xpath_explorer.core.constants')
sys.modules[__name__] = _impl

