# -*- coding: utf-8 -*-
"""Shared runtime utilities for XPath Explorer."""

import logging
from pathlib import Path


def setup_logger():
    """?? ??"""
    logger = logging.getLogger('XPathExplorer')
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S')
    console_handler.setFormatter(console_format)

    log_dir = Path.home() / '.xpath_explorer'
    log_dir.mkdir(exist_ok=True)
    file_handler = logging.FileHandler(log_dir / 'debug.log', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter('%(asctime)s [%(levelname)s] %(funcName)s:%(lineno)d - %(message)s')
    file_handler.setFormatter(file_format)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    return logger


logger = setup_logger()
