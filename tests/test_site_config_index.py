from xpath_explorer.core.config import SiteConfig, XPathItem


def test_get_item_uses_index_after_add_update_remove():
    cfg = SiteConfig(name="t", url="https://example.com")
    a = XPathItem(name="a", xpath="//a", category="common")
    b = XPathItem(name="b", xpath="//b", category="common")

    cfg.add_or_update(a)
    cfg.add_or_update(b)
    item_a = cfg.get_item("a")
    item_b = cfg.get_item("b")
    assert item_a is not None
    assert item_b is not None
    assert item_a.xpath == "//a"
    assert item_b.xpath == "//b"

    cfg.add_or_update(XPathItem(name="a", xpath="//a2", category="common"))
    item_a2 = cfg.get_item("a")
    assert item_a2 is not None
    assert item_a2.xpath == "//a2"

    cfg.remove_item("b")
    assert cfg.get_item("b") is None


def test_replace_items_and_from_dict_rebuild_index():
    cfg = SiteConfig(name="t", url="https://example.com")
    cfg.replace_items(
        [
            XPathItem(name="x", xpath="//x", category="common"),
            XPathItem(name="y", xpath="//y", category="common"),
        ]
    )
    assert cfg.get_item("x") is not None
    assert cfg.get_item("y") is not None

    loaded = SiteConfig.from_dict(
        {
            "name": "loaded",
            "url": "https://example.com",
            "items": [
                {"name": "k1", "xpath": "//k1", "category": "c1"},
                {"name": "k2", "xpath": "//k2", "category": "c2"},
            ],
        }
    )
    item_k1 = loaded.get_item("k1")
    item_k2 = loaded.get_item("k2")
    assert item_k1 is not None
    assert item_k2 is not None
    assert item_k1.xpath == "//k1"
    assert item_k2.xpath == "//k2"
