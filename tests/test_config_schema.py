from xpath_explorer.core.config import CONFIG_SCHEMA_VERSION, SiteConfig


def test_site_config_to_dict_includes_schema_version():
    config = SiteConfig(name="site", url="https://example.com")

    payload = config.to_dict()

    assert payload["schema_version"] == CONFIG_SCHEMA_VERSION


def test_site_config_from_dict_normalizes_old_and_bad_optional_types():
    config = SiteConfig.from_dict(
        {
            "name": 123,
            "url": None,
            "schema_version": "1",
            "items": [
                {
                    "name": 1,
                    "xpath": 2,
                    "category": None,
                    "tags": "critical, login",
                    "test_count": "3",
                    "success_count": "9",
                    "is_favorite": "true",
                    "alternatives": [1, "//a"],
                    "element_attributes": {"id": 7},
                    "ai_generated": "yes",
                }
            ],
        }
    )

    item = config.items[0]

    assert config.name == "123"
    assert config.url == ""
    assert config.schema_version == 1
    assert item.name == "1"
    assert item.xpath == "2"
    assert item.category == "common"
    assert item.tags == ["critical", "login"]
    assert item.test_count == 3
    assert item.success_count == 3
    assert item.is_favorite is True
    assert item.alternatives == ["1", "//a"]
    assert item.element_attributes == {"id": "7"}
    assert item.ai_generated is True

