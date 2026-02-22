# -*- coding: utf-8 -*-
"""
XPath Explorer Statistics Manager
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Dict, List, Optional

from xpath_constants import STATISTICS_SAVE_INTERVAL
from xpath_perf import perf_span

logger = logging.getLogger("XPathExplorer")


@dataclass
class TestRecord:
    item_name: str
    xpath: str
    success: bool
    timestamp: str
    frame_path: str = ""
    error_msg: str = ""


@dataclass
class ItemStatistics:
    name: str
    total_tests: int = 0
    successful_tests: int = 0
    failed_tests: int = 0
    last_test_time: str = ""
    last_success_time: str = ""
    last_failure_time: str = ""

    @property
    def success_rate(self) -> float:
        if self.total_tests == 0:
            return 0.0
        return (self.successful_tests / self.total_tests) * 100


class StatisticsManager:
    """Thread-safe statistics manager with async batched persistence."""

    def __init__(self, storage_path: Path = None):
        if storage_path is None:
            storage_path = Path.home() / ".xpath_explorer" / "statistics.json"

        self.storage_path = storage_path
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        self._stats: Dict[str, ItemStatistics] = {}
        self._history: List[TestRecord] = []
        self._save_interval = STATISTICS_SAVE_INTERVAL
        self._max_history = 500
        self._lock = Lock()

        self._dirty = False
        self._stop_event = Event()
        self._flush_event = Event()
        self._flush_done_event = Event()

        self._load()

        self._writer_thread = Thread(
            target=self._writer_loop,
            name="XPathStatsWriter",
            daemon=True,
        )
        self._writer_thread.start()

    def _load(self):
        if not self.storage_path.exists():
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            with self._lock:
                for name, stat_data in data.get("stats", {}).items():
                    self._stats[name] = ItemStatistics(**stat_data)
                for record_data in data.get("history", [])[-self._max_history :]:
                    self._history.append(TestRecord(**record_data))
        except json.JSONDecodeError as e:
            logger.error("Statistics file is corrupted, reinitializing: %s", e)
            try:
                backup_path = self.storage_path.with_suffix(".json.bak")
                self.storage_path.rename(backup_path)
            except Exception:
                pass
        except Exception as e:
            logger.error("Failed to load statistics: %s", e)

    def _writer_loop(self):
        while not self._stop_event.is_set():
            flush_requested = self._flush_event.wait(timeout=self._save_interval)
            if self._stop_event.is_set():
                break
            if flush_requested:
                self._flush_event.clear()
            if flush_requested or self._dirty:
                self._save_internal()
            if flush_requested:
                self._flush_done_event.set()

        # Final flush on shutdown
        if self._dirty:
            self._save_internal()
        if self._flush_event.is_set():
            self._flush_event.clear()
            self._flush_done_event.set()

    def _serialize(self) -> Dict:
        with self._lock:
            return {
                "stats": {name: asdict(stat) for name, stat in self._stats.items()},
                "history": [asdict(r) for r in self._history[-self._max_history :]],
            }

    def _save_internal(self):
        try:
            data = self._serialize()
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            with self._lock:
                self._dirty = False
        except Exception as e:
            logger.error("Failed to save statistics: %s", e)

    def save(self):
        """
        Immediate flush (public API compatibility).
        Blocks until async writer persisted pending data.
        """
        if not self._writer_thread.is_alive():
            self._save_internal()
            return
        self._flush_done_event.clear()
        self._flush_event.set()
        self._flush_done_event.wait(timeout=max(1.0, self._save_interval * 2))

    def shutdown(self, timeout: float = 5.0):
        """Flush pending data and stop background writer."""
        self.save()
        self._stop_event.set()
        self._flush_event.set()
        if self._writer_thread.is_alive():
            self._writer_thread.join(timeout=timeout)
        if self._writer_thread.is_alive():
            logger.warning("Statistics writer thread did not stop in time; forcing sync save.")
            self._save_internal()

    def record_test(
        self,
        item_name: str,
        xpath: str,
        success: bool,
        frame_path: str = "",
        error_msg: str = "",
    ):
        with perf_span("stats.record_test"):
            now = datetime.now().isoformat()

            with self._lock:
                if item_name not in self._stats:
                    self._stats[item_name] = ItemStatistics(name=item_name)

                stat = self._stats[item_name]
                stat.total_tests += 1
                stat.last_test_time = now
                if success:
                    stat.successful_tests += 1
                    stat.last_success_time = now
                else:
                    stat.failed_tests += 1
                    stat.last_failure_time = now

                self._history.append(
                    TestRecord(
                        item_name=item_name,
                        xpath=xpath,
                        success=success,
                        timestamp=now,
                        frame_path=frame_path,
                        error_msg=error_msg,
                    )
                )
                if len(self._history) > self._max_history:
                    self._history = self._history[-self._max_history :]

                self._dirty = True

    def get_item_stats(self, item_name: str) -> Optional[ItemStatistics]:
        with self._lock:
            return self._stats.get(item_name)

    def get_all_stats(self) -> Dict[str, ItemStatistics]:
        with self._lock:
            return self._stats.copy()

    def get_summary(self) -> Dict:
        with self._lock:
            total_items = len(self._stats)
            total_tests = sum(s.total_tests for s in self._stats.values())
            total_success = sum(s.successful_tests for s in self._stats.values())
            total_failure = sum(s.failed_tests for s in self._stats.values())

        avg_success_rate = (total_success / total_tests * 100) if total_tests > 0 else 0.0
        return {
            "total_items": total_items,
            "total_tests": total_tests,
            "total_success": total_success,
            "total_failure": total_failure,
            "average_success_rate": avg_success_rate,
        }

    def get_unstable_items(self, threshold: float = 80.0) -> List[ItemStatistics]:
        with self._lock:
            unstable = [
                stat
                for stat in self._stats.values()
                if stat.total_tests > 0 and stat.success_rate < threshold
            ]
        return sorted(unstable, key=lambda x: x.success_rate)

    def get_recent_history(self, limit: int = 50) -> List[TestRecord]:
        with self._lock:
            return list(reversed(self._history[-limit:]))

    def get_item_history(self, item_name: str, limit: int = 20) -> List[TestRecord]:
        with self._lock:
            item_records = [r for r in self._history if r.item_name == item_name]
            return list(reversed(item_records[-limit:]))

    def clear_statistics(self):
        with self._lock:
            self._stats.clear()
            self._history.clear()
            self._dirty = True
        self.save()

    def clear_item_statistics(self, item_name: str):
        with self._lock:
            if item_name in self._stats:
                del self._stats[item_name]
            self._history = [r for r in self._history if r.item_name != item_name]
            self._dirty = True
        self.save()

