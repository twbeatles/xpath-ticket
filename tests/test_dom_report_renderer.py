from xpath_explorer.browser.dom_export import DomSnapshot, render_dom_report_htm


def test_render_dom_report_htm_contains_summary_toc_and_escaped_dom():
    snapshots = [
        DomSnapshot(
            engine="selenium",
            window_id="w-main",
            window_title="Main Window",
            window_url="https://main.example",
            is_popup=False,
            frame_path="main",
            frame_label="main",
            document_url="https://main.example",
            html="<div>한글 & <span>unsafe</span></div>",
        ),
        DomSnapshot(
            engine="playwright",
            window_id="w-popup",
            window_title="Popup Window",
            window_url="https://popup.example",
            is_popup=True,
            frame_path="frameA",
            frame_label="frameA",
            document_url="https://popup.example/frameA",
            html="",
            error="frame detached",
            error_type="detached_frame",
        ),
    ]

    output = render_dom_report_htm(
        snapshots,
        source_label="Test Source",
        generated_at_iso="2026-02-25T12:00:00",
        scope="current",
        selected_window_title="Popup Window",
        selected_window_url="https://popup.example",
    )

    assert "Test Source DOM Export Report" in output
    assert "<strong>Total Documents:</strong> 2" in output
    assert "<strong>Failed Documents:</strong> 1" in output
    assert "<strong>Scope:</strong> current" in output
    assert "<strong>Selected Window:</strong> Popup Window" in output
    assert "<strong>Selected URL:</strong> https://popup.example" in output
    assert "<strong>Error Types:</strong> detached_frame=1" in output
    assert "href='#doc-1'" in output
    assert "href='#doc-2'" in output
    assert "&lt;div&gt;한글 &amp; &lt;span&gt;unsafe&lt;/span&gt;&lt;/div&gt;" in output
    assert "수집 실패 (detached_frame)" in output
    assert "frame detached" in output
