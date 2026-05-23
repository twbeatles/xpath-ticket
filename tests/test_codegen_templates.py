import ast

from xpath_explorer.tools.codegen import ActionStep, CodeGenerator, CodeTemplate
from xpath_explorer.core.config import SiteConfig, XPathItem


def test_codegen_all_templates_generate_without_error():
    items = SiteConfig.from_preset("인터파크").items[:3]
    generator = CodeGenerator()

    for template in (
        CodeTemplate.SELENIUM_PYTHON,
        CodeTemplate.PLAYWRIGHT_PYTHON,
        CodeTemplate.PYAUTOGUI,
    ):
        code = generator.generate(items, template)
        assert isinstance(code, str)
        assert code.strip()


def test_codegen_python_templates_are_syntax_valid():
    items = SiteConfig.from_preset("인터파크").items[:3]
    generator = CodeGenerator()

    selenium_code = generator.generate(items, CodeTemplate.SELENIUM_PYTHON)
    playwright_code = generator.generate(items, CodeTemplate.PLAYWRIGHT_PYTHON)

    ast.parse(selenium_code)
    ast.parse(playwright_code)


def test_codegen_actions_use_xpath_mapping_and_safe_literals():
    items = SiteConfig.from_preset("인터파크").items[:2]
    generator = CodeGenerator()

    actions = [
        ActionStep(action="click", xpath=items[0].xpath, description="기존 항목 클릭"),
        ActionStep(action="type", xpath='//input[@name="q"]', value='a"b\'c', description="검색어 입력"),
    ]

    code = generator.generate(items, CodeTemplate.SELENIUM_PYTHON, actions)
    ast.parse(code)
    assert "XPathConstants." in code
    assert "//input[@name=\\\"q\\\"]" in code


def test_codegen_includes_window_and_frame_context_metadata():
    item = XPathItem(
        name="seat button",
        xpath="//button[@id='seat']",
        category="ticket",
        found_frame="ifrmSeat/index=0",
        found_window_title="예매 팝업",
        found_window_url="https://ticket.example/popup",
        source_engine="playwright",
    )
    generator = CodeGenerator()
    actions = [ActionStep(action="click", xpath=item.xpath, description="좌석 클릭")]

    selenium_code = generator.generate([item], CodeTemplate.SELENIUM_PYTHON, actions)
    playwright_code = generator.generate([item], CodeTemplate.PLAYWRIGHT_PYTHON, actions)

    ast.parse(selenium_code)
    ast.parse(playwright_code)
    assert "ITEM_CONTEXTS" in selenium_code
    assert "ifrmSeat/index=0" in selenium_code
    assert "예매 팝업" in selenium_code
    assert "context=XPathConstants.ITEM_CONTEXTS.get" in selenium_code
    assert "context=XPathConstants.ITEM_CONTEXTS.get" in playwright_code
