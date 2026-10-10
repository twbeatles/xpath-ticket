# -*- coding: utf-8 -*-
"""Crash-recovery autosave for the unsaved XPath item list.

Best-effort by design: every function swallows its own errors so a broken
home directory can never interrupt editing. The snapshot is cleared on
explicit save/open/new-config; a leftover snapshot means the previous
session ended without saving.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from xpath_explorer.core.paths import atomic_write_json, resolve_storage_file

AUTOSAVE_FILENAME = "autosave.json"


def autosave_path() -> Optional[Path]:
    path, _source = resolve_storage_file(AUTOSAVE_FILENAME)
    return path


def write_autosave(config: Any) -> bool:
    """Persist the current config snapshot. Returns False when impossible."""
    path = autosave_path()
    if path is None:
        return False
    try:
        payload = {
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "config": config.to_dict() if hasattr(config, "to_dict") else {},
        }
        atomic_write_json(path, payload, backup=False)
        return True
    except Exception:
        return False


def read_autosave() -> Optional[Dict[str, Any]]:
    """Return the snapshot payload, or None when missing/unreadable."""
    path = autosave_path()
    if path is None or not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception:
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("config"), dict):
        return None
    return payload


def clear_autosave() -> None:
    path = autosave_path()
    if path is None:
        return
    try:
        if path.exists():
            path.unlink()
    except Exception:
        pass


def _fingerprint_config_dict(config_dict: Any) -> str:
    return json.dumps(config_dict, sort_keys=True, ensure_ascii=False, default=str)


def is_autosave_restorable(config: Any, payload: Dict[str, Any]) -> bool:
    """True when the snapshot differs from the current config."""
    current = config.to_dict() if hasattr(config, "to_dict") else {}
    saved = payload.get("config") or {}
    return _fingerprint_config_dict(current) != _fingerprint_config_dict(saved)
