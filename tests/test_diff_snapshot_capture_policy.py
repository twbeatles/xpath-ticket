import importlib.util
from pathlib import Path

from xpath_config import SiteConfig, XPathItem


def _load_main_module():
    root = Path(__file__).resolve().parent.parent
    path = root / "xpath 조사기(모든 티켓 사이트).py"
    spec = importlib.util.spec_from_file_location("xpath_main_module", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _FakeBrowser:
    def __init__(self):
        self.include_attributes_calls = []

    def get_element_info(self, xpath, frame_path=None, include_attributes=True, session=None):
        self.include_attributes_calls.append(include_attributes)
        attrs = {"id": "a1", "class": "btn"} if include_attributes else {}
        return {
            "found": True,
            "tag": "button",
            "id": "a1",
            "class": "btn",
            "text": "ok",
            "count": 1,
            "attributes": attrs,
            "frame_path": frame_path or "main",
        }


class _FakeDiff:
    def __init__(self):
        self._names = set()
        self.save_calls = 0

    def has_snapshot(self, item_name):
        return item_name in self._names

    def save_snapshot(self, item_name, _payload):
        self.save_calls += 1
        self._names.add(item_name)


class _FakeStats:
    def __init__(self):
        self.calls = 0

    def record_test(self, *args, **kwargs):
        self.calls += 1


def test_record_validation_outcome_only_collects_full_attrs_for_initial_snapshot():
    module = _load_main_module()
    explorer = module.XPathExplorer.__new__(module.XPathExplorer)

    item = XPathItem(name="target", xpath="//button[@id='a1']", category="common")
    explorer.config = SiteConfig(name="test", url="", items=[item])
    explorer.browser = _FakeBrowser()
    explorer.diff_analyzer = _FakeDiff()
    explorer.stats_manager = _FakeStats()
    explorer.table_model = None

    module.XPathExplorer._record_validation_outcome(
        explorer,
        name="target",
        xpath=item.xpath,
        success=True,
        result={"found": True, "tag": "button", "frame_path": "main"},
    )
    module.XPathExplorer._record_validation_outcome(
        explorer,
        name="target",
        xpath=item.xpath,
        success=True,
        result={"found": True, "tag": "button", "frame_path": "main"},
    )

    assert explorer.browser.include_attributes_calls == [True, False]
    assert explorer.diff_analyzer.save_calls == 1
    assert explorer.stats_manager.calls == 2

