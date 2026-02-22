#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Legacy entrypoint wrapper for XPath Explorer."""

from xpath_explorer.main_window import XPathExplorer, main
from xpath_explorer.runtime import logger, setup_logger

__all__ = ["XPathExplorer", "main", "setup_logger", "logger"]


if __name__ == "__main__":
    main()
