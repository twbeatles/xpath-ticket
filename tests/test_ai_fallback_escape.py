from xpath_explorer.tools.ai import XPathAIAssistant


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


def test_openai_generate_handles_missing_message_content():
    assistant = XPathAIAssistant(api_key="sk-test-key")
    assistant._provider = "openai"

    class _Message:
        content = None

    class _Choice:
        message = _Message()

    class _Completions:
        def create(self, **_kwargs):
            return type("Resp", (), {"choices": [_Choice()]})()

    class _Chat:
        completions = _Completions()

    assistant._client = type("Client", (), {"chat": _Chat()})()

    result = assistant._generate_with_openai("system", "user")

    assert result.xpath == ""
    assert result.confidence == 0.0
    assert "기본값" in result.explanation


def test_openai_generate_coerces_invalid_confidence_type():
    assistant = XPathAIAssistant(api_key="sk-test-key")
    assistant._provider = "openai"

    class _Message:
        content = '{"xpath": "//button", "confidence": "high", "alternatives": [1, "//*[@id=\\"x\\"]"]}'

    class _Choice:
        message = _Message()

    class _Completions:
        def create(self, **_kwargs):
            return type("Resp", (), {"choices": [_Choice()]})()

    class _Chat:
        completions = _Completions()

    assistant._client = type("Client", (), {"chat": _Chat()})()

    result = assistant._generate_with_openai("system", "user")

    assert result.xpath == "//button"
    assert result.confidence == 0.0
    assert result.alternative_xpaths == ["1", '//*[@id="x"]']
