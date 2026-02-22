from xpath_ai import XPathAIAssistant


def test_xpath_text_expr_handles_mixed_quotes():
    assistant = XPathAIAssistant(api_key="")
    expr = assistant._xpath_text_expr('a"b\'c')
    assert expr.startswith("concat(")
    assert "'\"'" in expr


def test_fallback_button_xpath_escapes_mixed_quotes():
    assistant = XPathAIAssistant(api_key="")
    result = assistant._fallback_suggestion('로그인 "빠른" 버튼 \'즉시\'')
    assert result.xpath.startswith("//button")
    assert "concat(" in result.xpath


def test_fallback_default_xpath_escapes_mixed_quotes():
    assistant = XPathAIAssistant(api_key="")
    result = assistant._fallback_suggestion('특수 "문자" 와 \'따옴표\' 포함 텍스트')
    assert result.xpath.startswith("//*[contains(text(), ")
    assert "concat(" in result.xpath
