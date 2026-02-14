from dataclasses import dataclass

from xpath_history import HistoryManager


@dataclass
class MockItem:
    name: str
    xpath: str

    def to_dict(self):
        return {"name": self.name, "xpath": self.xpath}


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
