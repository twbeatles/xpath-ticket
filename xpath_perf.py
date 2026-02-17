# -*- coding: utf-8 -*-
"""
XPath Explorer Performance Utilities
"""

from contextlib import contextmanager
import logging
import time
from typing import Optional

from xpath_constants import PERF_LOG_SLOW_MS

logger = logging.getLogger("XPathExplorer")


@contextmanager
def perf_span(name: str, threshold_ms: Optional[float] = None):
    """
    코드 블록의 실행 시간을 측정하고, 임계값 이상일 때 DEBUG 로그를 남깁니다.

    Args:
        name: 측정 구간 이름
        threshold_ms: 로그 출력 임계값(ms). None이면 PERF_LOG_SLOW_MS 사용.
    """
    threshold = PERF_LOG_SLOW_MS if threshold_ms is None else threshold_ms
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        if elapsed_ms >= threshold:
            logger.debug("[PERF] %s took %.2f ms", name, elapsed_ms)
