from xpath_explorer.analysis.statistics import StatisticsManager


def test_statistics_recent_history_returns_latest_first(tmp_path):
    path = tmp_path / "stats.json"
    manager = StatisticsManager(storage_path=path)

    manager.record_test("a", "//a", True)
    manager.record_test("b", "//b", False, error_msg="boom")
    manager.record_test("c", "//c", True)

    recent = manager.get_recent_history(limit=2)
    manager.shutdown(timeout=2.0)

    assert len(recent) == 2
    assert recent[0].item_name == "c"
    assert recent[1].item_name == "b"

