# -*- coding: utf-8 -*-
"""Compatibility facade for AI assistant classes."""

from xpath_explorer.ai.assistant import XPathAIAssistant
from xpath_explorer.ai.models import AIConfigResult, XPathSuggestion
from xpath_explorer.ai.providers import (
    DEFAULT_GEMINI_MODEL,
    DEFAULT_OPENAI_MODEL,
    SUPPORTED_PROVIDERS,
)
from xpath_explorer.core.optional_imports import import_optional
from xpath_explorer.core.paths import atomic_write_json, resolve_storage_file

__all__ = [
    "AIConfigResult",
    "DEFAULT_GEMINI_MODEL",
    "DEFAULT_OPENAI_MODEL",
    "SUPPORTED_PROVIDERS",
    "XPathAIAssistant",
    "XPathSuggestion",
    "atomic_write_json",
    "import_optional",
    "resolve_storage_file",
]
