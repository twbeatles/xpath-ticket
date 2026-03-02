from dataclasses import dataclass

from xpath_explorer.state.history import HISTORY_MAX_ELEMENT_ATTRIBUTES, HistoryManager


@dataclass
class MockItem:
    name: str
    xpath: str

    def to_dict(self):
        return {"name": self.name, "xpath": self.xpath}


@dataclass
class RichMockItem:
    name: str
    xpath: str
    alternatives: list[str]
    element_attributes: dict[str, str]
    screenshot_path: str

    def to_dict(self):
        return {
            "name": self.name,
            "xpath": self.xpath,
            "category": "common",
            "alternatives": list(self.alternatives),
            "element_attributes": dict(self.element_attributes),
            "screenshot_path": self.screenshot_path,
        }


def test_undo_redo_roundtrip():
    mgr = HistoryManager(max_history=10)
    items = [MockItem("a", "//a")]
    mgr.initialize(items)

    mgr.push_state(items, "add", "b", "add b")
    items.append(MockItem("b", "//b"))
    mgr.sync_current_state(items)

    restored = mgr.undo()
    assert restored is not None
    assert [x["name"] for x in restored] == ["a"]

    restored2 = mgr.redo()
    assert restored2 is not None
    assert [x["name"] for x in restored2] == ["a", "b"]


def test_max_history_is_enforced():
    mgr = HistoryManager(max_history=2)
    items = [MockItem("a", "//a")]
    mgr.initialize(items)

    for n in ["b", "c", "d"]:
        mgr.push_state(items, "add", n, f"add {n}")
        items.append(MockItem(n, f"//{n}"))

    # max_history=2 so undo stack should not grow without bound
    assert mgr.undo_count <= 2


def test_history_snapshot_preserves_metadata_and_truncates_attributes():
    attrs = {f"k{i:03d}": str(i) for i in range(HISTORY_MAX_ELEMENT_ATTRIBUTES + 8)}
    mgr = HistoryManager(max_history=10)
    items = [
        RichMockItem(
            name="target",
            xpath="//button[@id='target']",
            alternatives=["//*[@id='target']", "//button[contains(.,'확인')]"],
            element_attributes=attrs,
            screenshot_path="captures/target.png",
        )
    ]
    mgr.initialize(items)

    mgr.push_state(items, "update", "target", "before update")
    items[0].alternatives = ["//changed"]
    items[0].element_attributes = {"single": "value"}
    items[0].screenshot_path = ""
    mgr.sync_current_state(items)

    restored = mgr.undo()
    assert restored is not None
    assert restored[0]["alternatives"] == ["//*[@id='target']", "//button[contains(.,'확인')]"]
    assert restored[0]["screenshot_path"] == "captures/target.png"
    restored_attrs = restored[0]["element_attributes"]
    assert len(restored_attrs) == HISTORY_MAX_ELEMENT_ATTRIBUTES
    assert "k000" in restored_attrs
    assert f"k{HISTORY_MAX_ELEMENT_ATTRIBUTES - 1:03d}" in restored_attrs
    assert f"k{HISTORY_MAX_ELEMENT_ATTRIBUTES:03d}" not in restored_attrs
