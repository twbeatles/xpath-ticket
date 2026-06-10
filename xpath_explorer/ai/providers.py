# -*- coding: utf-8 -*-
"""AI provider constants and small helpers."""

DEFAULT_OPENAI_MODEL = "gpt-5.4"
DEFAULT_GEMINI_MODEL = "gemini-flash-latest"
SUPPORTED_PROVIDERS = {"openai", "gemini"}


def default_model_for_provider(provider: str) -> str:
    return DEFAULT_OPENAI_MODEL if provider == "openai" else DEFAULT_GEMINI_MODEL
