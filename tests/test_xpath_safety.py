import pytest

from xpath_explorer.tools.optimizer import XPathOptimizer
from xpath_explorer.tools.xpath_safety import (
    xpath_attr_contains,
    xpath_attr_equals,
    xpath_contains_text,
    xpath_literal,
)


def test_xpath_literal_handles_quotes_and_empty_values():
    assert xpath_literal("") == '""'
    assert xpath_literal("plain") == '"plain"'
    assert xpath_literal('a"b') == "'a\"b'"
    assert xpath_literal("a'b") == '"a\'b"'

    mixed = xpath_literal('a"b\'c')

    assert mixed == 'concat("a", \'"\', "b\'c")'


def test_xpath_attribute_helpers_escape_values_and_reject_bad_attribute_names():
    value = 'id"with\'quotes'

    assert xpath_attr_equals("data-x", value) == '@data-x=concat("id", \'"\', "with\'quotes")'
    assert xpath_attr_contains("class", value) == 'contains(@class, concat("id", \'"\', "with\'quotes"))'
    assert xpath_contains_text(value) == 'contains(text(), concat("id", \'"\', "with\'quotes"))'

    with pytest.raises(ValueError):
        xpath_attr_equals("bad attr", "x")


def test_optimizer_uses_safe_literals_for_id_name_class_data_and_text():
    optimizer = XPathOptimizer()
    alternatives = optimizer.generate_alternatives(
        {
            "tag": "button",
            "id": 'btn"main',
            "name": "go'now",
            "class": 'primary "quoted',
            "text": '예매 "VIP\'석"',
            "attributes": {"data-action": 'book"vip\'seat', "aria-label": "Book"},
            "parent_tag": "div",
            "parent_id": 'panel"root',
            "parent_class": "section",
            "index": 1,
        }
    )

    joined = "\n".join(alt.xpath for alt in alternatives)

    assert '//*[@id="btn"main"]' not in joined
    assert "concat(" in joined
    assert '@name="go\'now"' in joined
    assert "data-action=concat(" in joined
    assert "contains(text(), concat(" in joined

