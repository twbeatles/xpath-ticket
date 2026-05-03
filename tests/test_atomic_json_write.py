import json

import pytest

import xpath_explorer.core.paths as paths_module
from xpath_explorer.core.paths import atomic_write_json


def test_atomic_write_json_writes_target_and_backup(tmp_path):
    target = tmp_path / "config.json"
    target.write_text('{"old": true}', encoding="utf-8")

    atomic_write_json(target, {"new": True})

    assert json.loads(target.read_text(encoding="utf-8")) == {"new": True}
    assert json.loads((tmp_path / "config.json.bak").read_text(encoding="utf-8")) == {"old": True}


def test_atomic_write_json_keeps_existing_file_when_dump_fails(monkeypatch, tmp_path):
    target = tmp_path / "config.json"
    target.write_text('{"old": true}', encoding="utf-8")

    def boom(*_args, **_kwargs):
        raise RuntimeError("dump failed")

    monkeypatch.setattr(paths_module.json, "dump", boom)

    with pytest.raises(RuntimeError, match="dump failed"):
        atomic_write_json(target, {"new": True})

    assert json.loads(target.read_text(encoding="utf-8")) == {"old": True}
    assert not list(tmp_path.glob("*.tmp"))
    assert not list(tmp_path.glob(".*.tmp"))
