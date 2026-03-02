# -*- coding: utf-8 -*-
"""XPath Explorer history manager."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime
from threading import RLock
from typing import Any, Dict, List, Optional

from xpath_explorer.core.constants import HISTORY_MAX_SIZE

HISTORY_MAX_ELEMENT_ATTRIBUTES = 64


@dataclass
class HistoryState:
    """Single undo/redo snapshot."""

    items_snapshot: List[Dict]
    timestamp: str
    action: str
    item_name: str
    description: str = ""

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "HistoryState":
        return cls(**data)


class HistoryManager:
    """Thread-safe undo/redo state manager."""

    def __init__(self, max_history: int = HISTORY_MAX_SIZE):
        self._undo_stack: List[HistoryState] = []
        self._redo_stack: List[HistoryState] = []
        self._max_history = max_history
        self._current_state: Optional[List[Dict]] = None
        self._lock = RLock()

    def initialize(self, items: List[Any]):
        with self._lock:
            self._current_state = self._items_to_dicts(items)
            self._undo_stack.clear()
            self._redo_stack.clear()

    def push_state(self, items: List[Any], action: str, item_name: str, description: str = ""):
        with self._lock:
            if self._current_state is not None:
                state = HistoryState(
                    items_snapshot=deepcopy(self._current_state),
                    timestamp=datetime.now().isoformat(),
                    action=action,
                    item_name=item_name,
                    description=description,
                )
                self._undo_stack.append(state)
                if len(self._undo_stack) > self._max_history:
                    self._undo_stack.pop(0)

            self._current_state = self._items_to_dicts(items)
            self._redo_stack.clear()

    def sync_current_state(self, items: List[Any]):
        with self._lock:
            self._current_state = self._items_to_dicts(items)

    def undo(self) -> Optional[List[Dict]]:
        with self._lock:
            if not self.can_undo():
                return None

            if self._current_state is not None:
                self._redo_stack.append(
                    HistoryState(
                        items_snapshot=deepcopy(self._current_state),
                        timestamp=datetime.now().isoformat(),
                        action="redo_point",
                        item_name="",
                        description="Redo point",
                    )
                )

            prev_state = self._undo_stack.pop()
            self._current_state = deepcopy(prev_state.items_snapshot)
            return self._current_state

    def redo(self) -> Optional[List[Dict]]:
        with self._lock:
            if not self.can_redo():
                return None

            if self._current_state is not None:
                self._undo_stack.append(
                    HistoryState(
                        items_snapshot=deepcopy(self._current_state),
                        timestamp=datetime.now().isoformat(),
                        action="undo_point",
                        item_name="",
                        description="Undo point",
                    )
                )

            next_state = self._redo_stack.pop()
            self._current_state = deepcopy(next_state.items_snapshot)
            return self._current_state

    def can_undo(self) -> bool:
        with self._lock:
            return len(self._undo_stack) > 0

    def can_redo(self) -> bool:
        with self._lock:
            return len(self._redo_stack) > 0

    def get_undo_description(self) -> str:
        with self._lock:
            if self._undo_stack:
                state = self._undo_stack[-1]
                return f"{state.action}: {state.item_name}"
            return ""

    def get_redo_description(self) -> str:
        with self._lock:
            if self._redo_stack:
                state = self._redo_stack[-1]
                return f"Redo: {state.item_name}"
            return ""

    def get_history_list(self, limit: int = 20) -> List[Dict]:
        with self._lock:
            history: List[Dict[str, str]] = []
            for state in reversed(self._undo_stack[-limit:]):
                history.append(
                    {
                        "timestamp": state.timestamp,
                        "action": state.action,
                        "item_name": state.item_name,
                        "description": state.description,
                    }
                )
            return history

    def clear(self):
        with self._lock:
            self._undo_stack.clear()
            self._redo_stack.clear()

    def _items_to_dicts(self, items: List[Any]) -> List[Dict]:
        """
        Convert item objects to dict snapshots.

        Policy:
        - Keep alternatives and screenshot_path.
        - Keep element_attributes but cap to 64 keys.
        """
        result: List[Dict] = []
        for item in items:
            if hasattr(item, "to_dict"):
                item_dict = item.to_dict()
            elif hasattr(item, "__dict__"):
                item_dict = dict(item.__dict__)
            else:
                item_dict = dict(item)

            optimized = dict(item_dict)

            attrs = optimized.get("element_attributes", {})
            if isinstance(attrs, dict):
                trimmed_attrs: Dict[Any, Any] = {}
                for idx, (key, value) in enumerate(attrs.items()):
                    if idx >= HISTORY_MAX_ELEMENT_ATTRIBUTES:
                        break
                    trimmed_attrs[key] = value
                optimized["element_attributes"] = trimmed_attrs
            else:
                optimized["element_attributes"] = {}

            optimized.setdefault("alternatives", [])
            optimized.setdefault("screenshot_path", "")
            result.append(optimized)
        return result

    @property
    def undo_count(self) -> int:
        with self._lock:
            return len(self._undo_stack)

    @property
    def redo_count(self) -> int:
        with self._lock:
            return len(self._redo_stack)
