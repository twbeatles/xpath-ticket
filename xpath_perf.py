# -*- coding: utf-8 -*-
"""
XPath Explorer Performance Utilities
"""

from contextlib import contextmanager
import logging
import time
from typing import Optional
from collections import defaultdict
from threading import Lock

from xpath_constants import PERF_LOG_SLOW_MS

logger = logging.getLogger("XPathExplorer")
_PERF_LOCK = Lock()
_PERF_SAMPLES = defaultdict(list)  # name -> elapsed ms samples
_MAX_SAMPLES_PER_SPAN = 2000


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
        _record_perf_sample(name, elapsed_ms)
        if elapsed_ms >= threshold:
            logger.debug("[PERF] %s took %.2f ms", name, elapsed_ms)


def _record_perf_sample(name: str, elapsed_ms: float):
    with _PERF_LOCK:
        samples = _PERF_SAMPLES[name]
        samples.append(elapsed_ms)
        if len(samples) > _MAX_SAMPLES_PER_SPAN:
            # Keep recent samples to cap memory while preserving current behavior trends.
            del samples[: len(samples) - _MAX_SAMPLES_PER_SPAN]


def get_perf_snapshot():
    """
    Return aggregated performance metrics per span.

    Returns:
        {
            span_name: {
                "count": int,
                "avg_ms": float,
                "p95_ms": float,
                "max_ms": float,
            },
            ...
        }
    """
    with _PERF_LOCK:
        copied = {name: list(samples) for name, samples in _PERF_SAMPLES.items()}

    snapshot = {}
    for name, samples in copied.items():
        if not samples:
            continue
        sorted_samples = sorted(samples)
        count = len(sorted_samples)
        p95_idx = min(count - 1, max(0, int(count * 0.95) - 1))
        snapshot[name] = {
            "count": count,
            "avg_ms": sum(sorted_samples) / count,
            "p95_ms": sorted_samples[p95_idx],
            "max_ms": sorted_samples[-1],
        }
    return snapshot


def log_perf_summary(top_n: int = 20):
    """Log aggregated perf summary for the slowest spans by p95."""
    snapshot = get_perf_snapshot()
    if not snapshot:
        logger.info("[PERF] No span metrics collected.")
        return

    ordered = sorted(
        snapshot.items(),
        key=lambda kv: (kv[1]["p95_ms"], kv[1]["avg_ms"], kv[1]["count"]),
        reverse=True,
    )
    logger.info("[PERF] ===== Perf Summary (top %d by p95) =====", min(top_n, len(ordered)))
    for name, metric in ordered[:top_n]:
        logger.info(
            "[PERF] %-32s count=%5d avg=%7.2fms p95=%7.2fms max=%7.2fms",
            name,
            metric["count"],
            metric["avg_ms"],
            metric["p95_ms"],
            metric["max_ms"],
        )
