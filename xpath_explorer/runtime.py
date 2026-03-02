# -*- coding: utf-8 -*-
"""Shared runtime utilities for XPath Explorer."""

import logging
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from typing import Dict, List

from xpath_explorer.core.paths import resolve_storage_file


@dataclass(frozen=True)
class ErrorTelemetryEvent:
    """Captured runtime error event."""

    timestamp_iso: str
    logger_name: str
    level: str
    module: str
    function: str
    line: int
    message: str


class ErrorTelemetryStore:
    """In-memory error telemetry store (thread-safe)."""

    def __init__(self, max_events: int = 500):
        self.max_events = max_events
        self._events: List[ErrorTelemetryEvent] = []
        self._counter: Counter[str] = Counter()
        self._critical_count = 0
        self._lock = Lock()

    @staticmethod
    def _event_key(event: ErrorTelemetryEvent) -> str:
        return f"{event.module}|{event.function}|{event.message}"

    @staticmethod
    def _escape_markdown_table_cell(value: str) -> str:
        text = str(value or "")
        text = text.replace("\\", "\\\\")
        text = text.replace("`", "\\`")
        text = text.replace("|", "\\|")
        text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")
        return text

    def record(self, record: logging.LogRecord):
        if record.levelno < logging.ERROR:
            return

        try:
            message = record.getMessage()
        except Exception:
            message = str(record.msg)

        event = ErrorTelemetryEvent(
            timestamp_iso=datetime.now().isoformat(timespec="seconds"),
            logger_name=record.name,
            level=record.levelname,
            module=record.module,
            function=record.funcName,
            line=int(record.lineno or 0),
            message=message,
        )

        key = self._event_key(event)
        with self._lock:
            self._events.append(event)
            if len(self._events) > self.max_events:
                self._events = self._events[-self.max_events :]
            self._counter[key] += 1
            if record.levelno >= logging.CRITICAL:
                self._critical_count += 1

    def clear(self):
        with self._lock:
            self._events.clear()
            self._counter.clear()
            self._critical_count = 0

    def get_recent_events(self, limit: int = 50) -> List[ErrorTelemetryEvent]:
        with self._lock:
            recent = self._events[-max(1, limit) :]
            return list(reversed(recent))

    def get_summary(self, top_n: int = 10) -> Dict:
        with self._lock:
            top_entries = self._counter.most_common(max(1, top_n))
            total_errors = sum(self._counter.values())
            buffered_events = len(self._events)
            critical_count = self._critical_count
            unique_error_types = len(self._counter)

            top_errors = []
            for key, count in top_entries:
                module, function, message = key.split("|", 2)
                top_errors.append(
                    {
                        "count": count,
                        "module": module,
                        "function": function,
                        "message": message,
                    }
                )

        return {
            "total_errors": total_errors,
            "critical_count": critical_count,
            "buffered_events": buffered_events,
            "unique_error_types": unique_error_types,
            "top_errors": top_errors,
        }

    def render_markdown_report(self, top_n: int = 10, recent_limit: int = 50) -> str:
        summary = self.get_summary(top_n=top_n)
        recent = self.get_recent_events(limit=recent_limit)

        lines = [
            "# Error Telemetry Report",
            "",
            f"- Generated At: {datetime.now().isoformat(timespec='seconds')}",
            f"- Total Errors: **{summary['total_errors']}**",
            f"- Critical Errors: **{summary['critical_count']}**",
            f"- Buffered Recent Events: **{summary['buffered_events']}**",
            "",
            "## Top Error Types",
            "",
            "| Count | Module | Function | Message |",
            "|---:|---|---|---|",
        ]
        for row in summary["top_errors"]:
            module = self._escape_markdown_table_cell(row["module"])
            function = self._escape_markdown_table_cell(row["function"])
            message = self._escape_markdown_table_cell(row["message"])
            lines.append(
                f"| {row['count']} | `{module}` | `{function}` | {message} |"
            )
        if not summary["top_errors"]:
            lines.append("| 0 | - | - | No errors captured |")

        lines.extend(
            [
                "",
                "## Recent Error Events",
                "",
                "| Time | Level | Location | Message |",
                "|---|---|---|---|",
            ]
        )
        for event in recent:
            location = self._escape_markdown_table_cell(f"{event.module}.{event.function}:{event.line}")
            level = self._escape_markdown_table_cell(event.level)
            message = self._escape_markdown_table_cell(event.message)
            lines.append(
                f"| {event.timestamp_iso} | {level} | `{location}` | {message} |"
            )
        if not recent:
            lines.append("| - | - | - | No recent events |")

        return "\n".join(lines)


class ErrorTelemetryHandler(logging.Handler):
    """Logging handler that captures ERROR+ records into telemetry store."""

    def __init__(self, store: ErrorTelemetryStore):
        super().__init__(level=logging.ERROR)
        self._store = store

    def emit(self, record: logging.LogRecord):
        self._store.record(record)


error_telemetry = ErrorTelemetryStore()


def setup_logger():
    """Shared app logger setup."""
    logger = logging.getLogger('XPathExplorer')
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S')
        console_handler.setFormatter(console_format)
        logger.addHandler(console_handler)

        log_path, source = resolve_storage_file("debug.log")
        if log_path is None:
            logger.warning("File logging disabled (in-memory mode: no writable storage path).")
        else:
            try:
                file_handler = logging.FileHandler(log_path, encoding='utf-8')
                file_handler.setLevel(logging.DEBUG)
                file_format = logging.Formatter('%(asctime)s [%(levelname)s] %(funcName)s:%(lineno)d - %(message)s')
                file_handler.setFormatter(file_format)
                logger.addHandler(file_handler)
                if source != "home":
                    logger.warning("File logging fallback path in use: %s", source)
            except Exception as e:
                logger.warning(f"File logging disabled (console only): {e}")

    has_telemetry_handler = any(isinstance(h, ErrorTelemetryHandler) for h in logger.handlers)
    if not has_telemetry_handler:
        logger.addHandler(ErrorTelemetryHandler(error_telemetry))

    return logger


logger = setup_logger()
