# -*- coding: utf-8 -*-
"""AI assistant data models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class XPathSuggestion:
    """AI가 제안한 XPath."""

    xpath: str
    confidence: float
    explanation: str
    alternative_xpaths: List[str]


@dataclass(frozen=True)
class AIConfigResult:
    """AI 설정 적용/저장 결과."""

    ok: bool
    config_saved: bool
    storage_source: str
    message: str
