# -*- coding: utf-8 -*-
"""Config dirty-state helpers."""

from __future__ import annotations

import json
from typing import Any


def config_fingerprint(config: Any) -> str:
    payload = config.to_dict() if hasattr(config, "to_dict") else {}
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)


def is_config_dirty(config: Any, saved_fingerprint: str | None) -> bool:
    if saved_fingerprint is None:
        return True
    return config_fingerprint(config) != saved_fingerprint
