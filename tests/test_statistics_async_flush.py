import json
import time

from xpath_explorer.analysis.statistics import StatisticsManager


def test_statistics_record_is_batched_and_shutdown_flushes(tmp_path):
    path = tmp_path / "stats.json"
    manager = StatisticsManager(storage_path=path)

    save_calls = {"n": 0}
    original_save_internal = manager._save_internal

    def wrapped_save_internal():
        save_calls["n"] += 1
        return original_save_internal()

    manager._save_internal = wrapped_save_internal

    for i in range(50):
        manager.record_test(
            item_name="item_a",
            xpath=f"//x[{i}]",
            success=(i % 2 == 0),
            frame_path="main",
            error_msg="",
        )

    # record_test path should not synchronously trigger file write.
    time.sleep(0.05)
    assert save_calls["n"] == 0

    manager.shutdown(timeout=2.0)

    assert save_calls["n"] >= 1
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "stats" in data
    assert "item_a" in data["stats"]
    assert data["stats"]["item_a"]["total_tests"] == 50


def test_statistics_falls_back_to_in_memory_when_storage_unavailable(monkeypatch):
    monkeypatch.setattr(
        "xpath_explorer.analysis.statistics.resolve_storage_file",
        lambda _name: (None, "memory"),
    )

    manager = StatisticsManager(storage_path=None)
    assert manager.storage_path is None

    manager.record_test("item_x", "//x", True, frame_path="main")
    manager.save()
    summary = manager.get_summary()
    manager.shutdown(timeout=2.0)

    assert summary["total_tests"] == 1
    assert summary["total_success"] == 1


def test_statistics_save_uses_atomic_json_writer(monkeypatch, tmp_path):
    path = tmp_path / "stats.json"
    calls = []

    def fake_atomic_write_json(target, payload):
        calls.append((target, payload))
        target.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(
        "xpath_explorer.analysis.statistics.atomic_write_json",
        fake_atomic_write_json,
    )

    manager = StatisticsManager(storage_path=path)
    manager.record_test("item_x", "//x", True, frame_path="main")
    manager.save()
    manager.shutdown(timeout=2.0)

    assert calls
    assert calls[0][0] == path

