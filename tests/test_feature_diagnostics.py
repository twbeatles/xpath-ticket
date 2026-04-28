from types import SimpleNamespace

from xpath_explorer.core.config import SiteConfig, XPathItem
from xpath_explorer.mixins.tools.inspection_tools import ExplorerInspectionToolsMixin


class _Stats:
    def get_recent_history(self, _limit):
        return [
            SimpleNamespace(
                success=False,
                timestamp="2026-04-28T10:00:00",
                item_name="login",
                frame_path="frame|a",
                error_msg="not|found",
            )
        ]


class _Host(ExplorerInspectionToolsMixin):
    def __init__(self):
        item = XPathItem(name="login", xpath="//button", category="common")
        item.found_window_title = "Popup"
        item.found_window_url = "https://popup.example"
        item.found_frame = "frame|a"
        self.config = SiteConfig(name="site", url="https://example.com", items=[item])
        self.browser = SimpleNamespace(
            current_frame_path="frame|a",
            is_alive=lambda: True,
            get_current_window_metadata=lambda: {
                "handle": "w1",
                "title": "Root",
                "url": "https://root.example",
            },
        )
        self.pw_manager = SimpleNamespace(
            is_alive=lambda: False,
            get_current_window_metadata=lambda: {},
            _current_frame=None,
        )
        self.stats_manager = _Stats()


def test_feature_diagnostics_markdown_contains_context_sections_and_escapes_tables():
    content = _Host()._render_feature_diagnostics_markdown()

    assert "# XPath Explorer 기능 진단 리포트" in content
    assert "## Selenium 상태" in content
    assert "## Playwright 상태" in content
    assert "## 저장 항목 문맥" in content
    assert "frame\\|a" in content
    assert "not\\|found" in content

