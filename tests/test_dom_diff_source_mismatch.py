from xpath_explorer.browser.dom_export import DomSnapshot
from xpath_explorer.mixins.tools_mixin import ExplorerToolsMixin


def _snapshot(source_label: str, html: str) -> DomSnapshot:
    return DomSnapshot(
        engine=source_label.lower(),
        window_id="w1",
        window_title="Example",
        window_url="https://example.com",
        is_popup=False,
        frame_path="main",
        frame_label="main",
        document_url="https://example.com",
        html=html,
    )


class _DiffHost(ExplorerToolsMixin):
    def __init__(self):
        self._dom_diff_baseline = [_snapshot("Selenium", "<html>old</html>")]
        self._dom_diff_source = "Selenium"
        self._toasts = []

    def _collect_active_dom_snapshots(self):
        return ([_snapshot("Playwright", "<html>new</html>")], "Playwright")

    def _show_toast(self, message, toast_type="info", duration=0):
        self._toasts.append((message, toast_type, duration))


def test_dom_diff_source_mismatch_resets_baseline_without_rendering_report():
    host = _DiffHost()

    host._export_dom_diff_report()

    assert host._dom_diff_source == "Playwright"
    assert host._dom_diff_baseline[0].html == "<html>new</html>"
    assert host._toasts
    assert host._toasts[-1][1] == "warning"

