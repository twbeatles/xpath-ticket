# -*- coding: utf-8 -*-
"""AI assistant configuration storage helpers."""

from __future__ import annotations

import json
import os
from logging import Logger
from typing import Any, Dict

from xpath_explorer.core.paths import resolve_storage_file

_AI_SECRET_KEYS = ("openai_api_key", "gemini_api_key")


def persistable_ai_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Drop API keys so they are not written to disk."""
    return {key: value for key, value in config.items() if key not in _AI_SECRET_KEYS}


def load_ai_config(logger: Logger) -> Dict[str, Any]:
    config: Dict[str, Any] = {}

    config_path, source = resolve_storage_file("ai_config.json")
    if config_path is not None and config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                file_config = json.load(f)
            if isinstance(file_config, dict):
                config.update(file_config)
        except Exception as e:
            logger.warning("AI config load failed from %s storage: %s", source, e)

    openai_key = os.environ.get("OPENAI_API_KEY")
    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if openai_key:
        config["openai_api_key"] = openai_key
    if gemini_key:
        config["gemini_api_key"] = gemini_key

    return config
