import json
import time

from xpath_statistics import StatisticsManager


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

