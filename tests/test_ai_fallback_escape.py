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


def test_external_page_context_redacts_sensitive_attribute_values(monkeypatch):
    assistant = XPathAIAssistant(api_key="sk-test-key")
    assistant._provider = "openai"
    captured = {}

    def fake_generate(system_prompt, user_prompt):
        captured["system_prompt"] = system_prompt
        captured["user_prompt"] = user_prompt
        return assistant._fallback_suggestion("x")

    monkeypatch.setattr(assistant, "_get_client", lambda: object())
    assistant._generate_with_openai = fake_generate

    assistant.generate_xpath_from_description(
        "로그인",
        page_context='<input value="secret@example.com" data-token="abc">',
    )

    assert "secret@example.com" not in captured["user_prompt"]
    assert 'value="[REDACTED]"' in captured["user_prompt"]


def test_external_page_context_can_be_disabled(monkeypatch):
    monkeypatch.setenv("XPATH_EXPLORER_AI_ALLOW_PAGE_CONTEXT", "0")
    assistant = XPathAIAssistant(api_key="")

    assert assistant._page_context_allowed() is False
