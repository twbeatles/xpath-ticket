# -*- coding: utf-8 -*-
"""Backward-compatible module shim.

Prefer importing from xpath_explorer.tools.codegen.
"""

import importlib
import sys

_impl = importlib.import_module('xpath_explorer.tools.codegen')
sys.modules[__name__] = _impl

