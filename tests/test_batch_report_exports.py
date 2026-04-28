import csv
import io

from xpath_explorer.mixins.tools.batch_tools import ExplorerBatchToolsMixin


def test_batch_results_csv_export_escapes_commas_quotes_and_newlines():
    rows = [
        {
            "success": False,
            "name": "login,button",
            "xpath": '//button[@id="x"]',
            "frame_path": "main",
            "window_title": 'Pop "A"',
            "msg": "line1\nline2",
            "error_type": "not_found",
        }
    ]

    content = ExplorerBatchToolsMixin._batch_results_to_csv(rows)
    parsed = list(csv.DictReader(io.StringIO(content)))

    assert parsed[0]["name"] == "login,button"
    assert parsed[0]["window_title"] == 'Pop "A"'
    assert parsed[0]["msg"] == "line1\nline2"
    assert parsed[0]["error_type"] == "not_found"


def test_batch_results_markdown_export_escapes_pipe_characters():
    rows = [{"success": True, "name": "a|b", "msg": "ok|done", "frame_path": "f1"}]

    content = ExplorerBatchToolsMixin._batch_results_to_markdown(rows, title="Result")

    assert "# Result" in content
    assert "a\\|b" in content
    assert "ok\\|done" in content

