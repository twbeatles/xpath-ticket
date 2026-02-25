from xpath_codegen import CodeGenerator


def test_xpath_template_library_has_minimum_templates():
    templates = CodeGenerator.list_xpath_templates()
    assert len(templates) >= 20
    categories = {template.category for template in templates}
    assert {"login", "booking", "seat", "common"}.issubset(categories)


def test_xpath_template_library_filters_by_category():
    login_templates = CodeGenerator.list_xpath_templates(category="login")
    assert login_templates
    assert all(template.category == "login" for template in login_templates)


def test_xpath_template_library_filters_by_keyword_case_insensitive():
    templates = CodeGenerator.list_xpath_templates(keyword="captcha")
    assert templates
    assert any("captcha" in template.xpath.lower() or "captcha" in template.description.lower() for template in templates)
