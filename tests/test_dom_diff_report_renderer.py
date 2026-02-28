from xpath_explorer.browser.dom_export import (
    DomSnapshot,
    diff_dom_snapshots,
    render_dom_diff_report_htm,
)


def _snap(window_id: str, frame_path: str, html: str, doc_url: str, title: str = "win"):
    return DomSnapshot(
        engine="selenium",
        window_id=window_id,
        window_title=title,
        window_url=f"https://{window_id}.example",
        is_popup=(window_id != "main"),
        frame_path=frame_path,
        frame_label=frame_path,
        document_url=doc_url,
        html=html,
        error="",
    )


def test_diff_dom_snapshots_detects_added_removed_changed():
    old = [
        _snap("main", "main", "<html>A</html>", "https://main.example"),
        _snap("popup", "main", "<html>B</html>", "https://popup.example"),
    ]
    new = [
        _snap("main", "main", "<html>A2</html>", "https://main.example"),
        _snap("main", "frame1", "<html>C</html>", "https://main.example#frame1"),
    ]

    entries = diff_dom_snapshots(old, new)
    kinds = [entry.change_type for entry in entries]
    assert kinds.count("added") == 1
    assert kinds.count("removed") == 1
    assert kinds.count("changed") == 1


def test_render_dom_diff_report_htm_contains_summary_counts():
    old = [_snap("main", "main", "<html>A</html>", "https://main.example")]
    new = [_snap("main", "main", "<html>A2</html>", "https://main.example")]

    report = render_dom_diff_report_htm(
        old,
        new,
        source_label="Selenium DOM",
        generated_at_iso="2026-02-25T18:00:00",
    )

    assert "Selenium DOM DOM Diff Report" in report
    assert "추가 0" in report
    assert "삭제 0" in report
    assert "변경 1" in report
    assert "2026-02-25T18:00:00" in report

