# -*- coding: utf-8 -*-
"""Backward-compatible module shim.

Prefer importing from xpath_explorer.browser.dom_export.
"""

import importlib
import sys

_impl = importlib.import_module('xpath_explorer.browser.dom_export')
sys.modules[__name__] = _impl

