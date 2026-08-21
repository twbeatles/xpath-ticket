from xpath_explorer.core.config import SiteConfig, XPathItem
from xpath_explorer.core.config_state import config_fingerprint, is_config_dirty


def test_config_fingerprint_changes_when_items_change():
    config = SiteConfig(name="site", url="https://example.com")
    before = config_fingerprint(config)
    config.add_or_update(XPathItem(name="a", xpath="//a", category="common"))
    after = config_fingerprint(config)
    assert before != after
    assert is_config_dirty(config, before) is True
    assert is_config_dirty(config, after) is False
