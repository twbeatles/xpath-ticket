# -*- coding: utf-8 -*-
"""
XPath Explorer AI Assistant v4.0
AI 기반 XPath 추천 모듈 (Google GenAI 통합)
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, cast

from xpath_explorer.core.paths import atomic_write_json, resolve_storage_file
from xpath_explorer.core.optional_imports import import_optional
from xpath_explorer.tools.xpath_safety import xpath_literal

logger = logging.getLogger("XPathExplorer")

DEFAULT_OPENAI_MODEL = "gpt-5.4"
DEFAULT_GEMINI_MODEL = "gemini-flash-latest"
SUPPORTED_PROVIDERS = {"openai", "gemini"}
AI_KEY_STORAGE_ENV = "XPATH_EXPLORER_AI_KEY_STORAGE"
AI_ALLOW_PAGE_CONTEXT_ENV = "XPATH_EXPLORER_AI_ALLOW_PAGE_CONTEXT"
AI_KEYRING_SERVICE = "XPathExplorer"
SENSITIVE_CONTEXT_RE = re.compile(
    r"""(?ix)
    \b(value|password|passwd|token|api[-_]?key|authorization|cookie|session|secret)
    \s*=\s*
    (["']).*?\2
    """
)


@dataclass
class XPathSuggestion:
    """AI가 제안한 XPath"""

    xpath: str
    confidence: float  # 0.0 - 1.0
    explanation: str
    alternative_xpaths: List[str]


@dataclass(frozen=True)
class AIConfigResult:
    """AI 설정 적용/저장 결과"""

    ok: bool
    config_saved: bool
    storage_source: str
    message: str
    secret_saved: bool = False
    secret_storage: str = "session"


class XPathAIAssistant:
    """AI 기반 XPath 추천 어시스턴트"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Args:
            api_key: OpenAI API 키 (없으면 환경변수 또는 설정 파일에서 로드)
        """
        self._client = None
        self._provider = "openai"
        self._model = DEFAULT_OPENAI_MODEL

        self._config = self._load_config()

        provider = self._coerce_text(self._config.get("provider"), default="openai").lower()
        if provider in SUPPORTED_PROVIDERS:
            self._provider = provider
        self._model = self._coerce_text(
            self._config.get("model"),
            default=self._default_model_for_provider(self._provider),
        )

        self._api_key = api_key or self._config.get(self._api_key_field(self._provider))

    @staticmethod
    def _api_key_field(provider: str) -> str:
        return f"{provider}_api_key"

    @staticmethod
    def _key_storage_mode() -> str:
        mode = os.environ.get(AI_KEY_STORAGE_ENV, "keyring").strip().lower()
        if mode in {"keyring", "plain", "env", "session"}:
            return mode
        return "keyring"

    @staticmethod
    def _page_context_allowed() -> bool:
        value = os.environ.get(AI_ALLOW_PAGE_CONTEXT_ENV, "1").strip().lower()
        return value not in {"0", "false", "no", "off"}

    @staticmethod
    def _load_api_key_from_keyring(provider: str) -> Optional[str]:
        keyring_module = import_optional("keyring")
        if keyring_module is None:
            return None
        try:
            value = keyring_module.get_password(AI_KEYRING_SERVICE, XPathAIAssistant._api_key_field(provider))
        except Exception as e:
            logger.debug("AI keyring load failed for %s: %s", provider, e)
            return None
        return value if isinstance(value, str) and value else None

    @staticmethod
    def _save_api_key_to_keyring(provider: str, api_key: str) -> bool:
        if not api_key:
            return False
        keyring_module = import_optional("keyring")
        if keyring_module is None:
            return False
        try:
            keyring_module.set_password(AI_KEYRING_SERVICE, XPathAIAssistant._api_key_field(provider), api_key)
            return True
        except Exception as e:
            logger.warning("AI keyring save failed for %s: %s", provider, e)
            return False

    @staticmethod
    def _without_plain_api_keys(config: Dict[str, Any]) -> Dict[str, Any]:
        sanitized = dict(config)
        for provider in SUPPORTED_PROVIDERS:
            sanitized.pop(XPathAIAssistant._api_key_field(provider), None)
        return sanitized

    @staticmethod
    def _sanitize_external_context(text: str, *, max_chars: int) -> str:
        if not text:
            return ""
        normalized = str(text).replace("\x00", "")
        redacted = SENSITIVE_CONTEXT_RE.sub(lambda m: f'{m.group(1)}="[REDACTED]"', normalized)
        return redacted[:max(0, int(max_chars))]

    @staticmethod
    def _default_model_for_provider(provider: str) -> str:
        return DEFAULT_OPENAI_MODEL if provider == "openai" else DEFAULT_GEMINI_MODEL

    def _load_config(self) -> Dict[str, Any]:
        """설정 로드"""
        config: Dict[str, Any] = {}

        openai_key = os.environ.get("OPENAI_API_KEY")
        gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

        if openai_key:
            config["openai_api_key"] = openai_key
        if gemini_key:
            config["gemini_api_key"] = gemini_key

        config_path, source = resolve_storage_file("ai_config.json")
        if config_path is not None and config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    file_config = json.load(f)
                if isinstance(file_config, dict):
                    config.update(file_config)
            except Exception as e:
                logger.warning("AI config load failed from %s storage: %s", source, e)

        for provider in SUPPORTED_PROVIDERS:
            key_field = self._api_key_field(provider)
            if not config.get(key_field):
                keyring_key = self._load_api_key_from_keyring(provider)
                if keyring_key:
                    config[key_field] = keyring_key

        return config

    def _load_api_key(self) -> Optional[str]:
        """Deprecated: Use _load_config instead"""
        if not hasattr(self, "_config") or not hasattr(self, "_provider"):
            return None
        return cast(Optional[str], self._config.get(f"{self._provider}_api_key"))

    def configure(
        self,
        api_key: str,
        model: Optional[str] = None,
        provider: str = "openai",
    ) -> AIConfigResult:
        """
        AI 설정

        Args:
            api_key: API 키
            model: 사용할 모델
            provider: 'openai' or 'gemini'

        Returns:
            AIConfigResult: 적용 및 저장 결과
        """
        provider = self._coerce_text(provider, default="openai").lower()
        if provider not in SUPPORTED_PROVIDERS:
            return AIConfigResult(
                ok=False,
                config_saved=False,
                storage_source="memory",
                message=f"지원하지 않는 AI 제공자입니다: {provider}",
            )

        api_key = self._coerce_text(api_key).strip()
        if len(api_key) < 10:
            return AIConfigResult(
                ok=False,
                config_saved=False,
                storage_source="memory",
                message="API 키 형식이 올바르지 않습니다.",
            )

        resolved_model = self._coerce_text(
            model,
            default=self._default_model_for_provider(provider),
        ).strip() or self._default_model_for_provider(provider)

        self._provider = provider
        self._api_key = api_key
        self._model = resolved_model
        self._client = None

        self._config["provider"] = provider
        self._config["model"] = self._model
        self._config[self._api_key_field(provider)] = api_key

        return self._save_config()

    def _save_config(self) -> AIConfigResult:
        config_path, source = resolve_storage_file("ai_config.json")
        mode = self._key_storage_mode()
        api_key = self._coerce_text(self._api_key or self._config.get(self._api_key_field(self._provider), ""))
        secret_saved = False
        secret_storage = "session"

        if mode == "plain":
            persisted_config = dict(self._config)
            secret_saved = bool(api_key)
            secret_storage = "plain-json"
        else:
            persisted_config = self._without_plain_api_keys(self._config)
            if mode == "env":
                secret_storage = "env"
            elif mode == "session":
                secret_storage = "session"
            else:
                secret_saved = self._save_api_key_to_keyring(self._provider, api_key)
                secret_storage = "keyring" if secret_saved else "session"

        if config_path is None:
            if secret_saved:
                message = "API 키는 안전 저장소에 저장되었지만 설정 파일 저장 경로가 없어 나머지 설정은 현재 세션에만 유지됩니다."
            else:
                message = "설정은 적용되었지만 저장 가능한 경로가 없어 현재 세션에만 유지됩니다."
            logger.warning("AI config save skipped: no writable storage path.")
            return AIConfigResult(
                ok=True,
                config_saved=False,
                storage_source=source,
                message=message,
                secret_saved=secret_saved,
                secret_storage=secret_storage,
            )

        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning("AI config directory init failed (%s): %s", source, e)
            return AIConfigResult(
                ok=True,
                config_saved=False,
                storage_source=source,
                message="설정은 적용되었지만 저장 디렉터리를 준비하지 못해 현재 세션에만 유지됩니다.",
                secret_saved=secret_saved,
                secret_storage=secret_storage,
            )

        try:
            atomic_write_json(config_path, persisted_config)
            if secret_saved:
                message = f"설정이 {source} 저장소에 저장되었고 API 키는 {secret_storage}에 저장되었습니다."
            elif mode == "plain":
                message = f"설정이 {source} 저장소에 저장되었습니다. API 키가 평문 JSON에 저장됩니다."
            else:
                message = f"설정이 {source} 저장소에 저장되었습니다. API 키는 현재 세션에만 유지됩니다."
            return AIConfigResult(
                ok=True,
                config_saved=True,
                storage_source=source,
                message=message,
                secret_saved=secret_saved,
                secret_storage=secret_storage,
            )
        except Exception as e:
            logger.warning("AI config save failed (%s): %s", source, e)
            return AIConfigResult(
                ok=True,
                config_saved=False,
                storage_source=source,
                message="설정은 적용되었지만 디스크 저장에 실패해 현재 세션에만 유지됩니다.",
                secret_saved=secret_saved,
                secret_storage=secret_storage,
            )

    def is_available(self) -> bool:
        """AI 기능 사용 가능 여부"""
        return bool(self._api_key)

    @staticmethod
    def _coerce_text(value: Any, default: str = "") -> str:
        if value is None:
            return default
        if isinstance(value, str):
            return value
        try:
            return str(value)
        except Exception:
            return default

    @staticmethod
    def _coerce_float(value: Any, default: float = 0.0) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default
        if number != number:
            return default
        return max(0.0, min(1.0, number))

    @classmethod
    def _coerce_string_list(cls, value: Any) -> List[str]:
        if not isinstance(value, (list, tuple)):
            return []
        results: List[str] = []
        for item in value:
            text = cls._coerce_text(item).strip()
            if text:
                results.append(text)
        return results

    @staticmethod
    def _safe_json_loads(payload: Any) -> Dict[str, Any]:
        if isinstance(payload, (bytes, bytearray)):
            payload = payload.decode("utf-8", errors="ignore")
        if not isinstance(payload, str):
            return {}
        payload = payload.strip()
        if not payload:
            return {}
        try:
            data = json.loads(payload)
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    def _build_xpath_suggestion(
        self,
        payload: Dict[str, Any],
        *,
        xpath_key: str = "xpath",
        fallback_xpath: str = "",
        fallback_explanation: str = "",
        confidence_default: float = 0.0,
    ) -> XPathSuggestion:
        return XPathSuggestion(
            xpath=self._coerce_text(payload.get(xpath_key), fallback_xpath),
            confidence=self._coerce_float(payload.get("confidence"), confidence_default),
            explanation=self._coerce_text(payload.get("explanation"), fallback_explanation),
            alternative_xpaths=self._coerce_string_list(payload.get("alternatives")),
        )

    @staticmethod
    def _extract_openai_content(response: Any) -> Optional[str]:
        try:
            choices = getattr(response, "choices", None) or []
            if not choices:
                return None
            message = getattr(choices[0], "message", None)
            content = getattr(message, "content", None)
            return content if isinstance(content, str) else None
        except Exception:
            return None

    @staticmethod
    def _build_gemini_generate_config(system_prompt: str) -> Optional[Any]:
        """Build GenerateContentConfig via dynamic import for optional dependency."""
        types_module = import_optional("google.genai.types")
        if types_module is None:
            return None

        config_cls = getattr(types_module, "GenerateContentConfig", None)
        if config_cls is None:
            return None

        return config_cls(
            system_instruction=system_prompt,
            response_mime_type="application/json",
        )

    def _get_client(self) -> Optional[Any]:
        """클라이언트 초기화 (Provider 분기)"""
        if self._client is not None:
            return self._client

        if not self._api_key:
            return None

        if self._provider == "openai":
            openai_module = import_optional("openai")
            if openai_module is None:
                raise ImportError("OpenAI 라이브러리가 필요합니다. pip install openai")
            openai_cls = getattr(openai_module, "OpenAI", None)
            if openai_cls is None:
                raise ImportError("openai.OpenAI not found")
            self._client = openai_cls(api_key=self._api_key)
        elif self._provider == "gemini":
            genai_module = import_optional("google.genai")
            if genai_module is None:
                raise ImportError("Google GenAI 라이브러리가 필요합니다. pip install google-genai")
            client_cls = getattr(genai_module, "Client", None)
            if client_cls is None:
                raise ImportError("google.genai.Client not found")
            self._client = client_cls(api_key=self._api_key)
        return self._client

    def _xpath_text_expr(self, text: str) -> str:
        """XPath 문자열 리터럴 표현식 생성 (따옴표 안전)"""
        return xpath_literal(text)

    def generate_xpath_from_description(
        self,
        description: str,
        page_context: Optional[str] = None,
        existing_xpaths: Optional[List[str]] = None,
    ) -> XPathSuggestion:
        """
        자연어 설명으로 XPath 생성

        Args:
            description: 요소에 대한 자연어 설명
            page_context: 페이지 HTML 일부
            existing_xpaths: 이미 저장된 XPath 목록

        Returns:
            XPathSuggestion 객체
        """
        client = self._get_client()
        if not client:
            return self._fallback_suggestion(description)

        system_prompt = """당신은 웹 자동화 전문가입니다.
사용자가 설명하는 웹 요소에 대해 가장 적합한 XPath를 생성합니다.

응답 형식 (JSON):
{
    "xpath": "추천 XPath",
    "confidence": 0.0-1.0 사이 신뢰도,
    "explanation": "이 XPath를 선택한 이유",
    "alternatives": ["대안 XPath 1", "대안 XPath 2"]
}

XPath 생성 시 고려사항:
1. ID가 있다면 ID 기반 XPath 우선
2. 안정적인 속성(data-*, name) 활용
3. 텍스트 기반 XPath는 contains() 사용 권장
4. 인덱스[n] 기반은 최후의 수단
5. 한국어/영어 텍스트 모두 고려"""

        user_prompt = f"다음 요소에 대한 XPath를 생성해주세요: {description}"

        if page_context:
            if self._page_context_allowed():
                safe_context = self._sanitize_external_context(page_context, max_chars=2000)
                user_prompt += f"\n\n페이지 컨텍스트(민감 속성 값은 제거됨):\n{safe_context}"
            else:
                user_prompt += "\n\n페이지 컨텍스트: 전송 비활성화됨"

        if existing_xpaths:
            user_prompt += "\n\n이미 존재하는 XPath (중복 방지):\n" + "\n".join(existing_xpaths[:10])

        try:
            if self._provider == "gemini":
                return self._generate_with_gemini(system_prompt, user_prompt)
            return self._generate_with_openai(system_prompt, user_prompt)
        except Exception as e:
            logger.warning("AI 요청 실패: %s", e)
            return self._fallback_suggestion(description)

    def _generate_with_gemini(self, system_prompt: str, user_prompt: str) -> XPathSuggestion:
        """Gemini API 사용하여 생성 (google-genai)"""
        client = self._get_client()
        if client is None:
            return self._fallback_suggestion(user_prompt)
        client = cast(Any, client)
        try:
            config = self._build_gemini_generate_config(system_prompt)
            response = client.models.generate_content(
                model=self._model,
                contents=user_prompt,
                **({"config": config} if config is not None else {})
            )
            result = self._safe_json_loads(getattr(response, "text", None))
            return self._build_xpath_suggestion(
                result,
                fallback_explanation="Gemini 응답을 해석하지 못해 기본값을 사용했습니다.",
            )
        except Exception as e:
            err_expr = self._xpath_text_expr(str(e))
            return XPathSuggestion(
                xpath=f"//error[contains(text(), {err_expr})]",
                confidence=0.0,
                explanation=f"AI 오류: {e}",
                alternative_xpaths=[],
            )

    def _generate_with_openai(self, system_prompt: str, user_prompt: str) -> XPathSuggestion:
        """OpenAI API 사용하여 생성"""
        client = self._get_client()
        if client is None:
            return self._fallback_suggestion(user_prompt)
        client = cast(Any, client)
        response = client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=500,
            response_format={"type": "json_object"},
        )
        result = self._safe_json_loads(self._extract_openai_content(response))
        return self._build_xpath_suggestion(
            result,
            fallback_explanation="OpenAI 응답을 해석하지 못해 기본값을 사용했습니다.",
        )

    def _fallback_suggestion(self, description: str) -> XPathSuggestion:
        """AI 없이 기본 XPath 제안 (규칙 기반)"""
        desc_lower = description.lower()

        if any(word in desc_lower for word in ["버튼", "button", "btn", "클릭"]):
            button_text = description.replace("버튼", "").replace("button", "").strip()
            if not button_text:
                button_text = description.strip()
            button_expr = self._xpath_text_expr(button_text)
            return XPathSuggestion(
                xpath=f"//button[contains(text(), {button_expr})]",
                confidence=0.6,
                explanation="텍스트 기반 버튼 XPath (AI 없이 규칙 기반 생성)",
                alternative_xpaths=[
                    f'//*[contains(@class, "btn")][contains(text(), {button_expr})]',
                    f"//input[@type=\"submit\"][@value={button_expr}]",
                ],
            )

        if any(word in desc_lower for word in ["입력", "input", "필드", "텍스트박스"]):
            field_type = "text"
            if "이메일" in desc_lower or "email" in desc_lower:
                field_type = "email"
            elif "비밀번호" in desc_lower or "password" in desc_lower:
                field_type = "password"
            description_expr = self._xpath_text_expr(description)
            field_type_expr = self._xpath_text_expr(field_type)
            return XPathSuggestion(
                xpath=f'//input[@type="{field_type}"]',
                confidence=0.5,
                explanation=f"{field_type} 타입 입력 필드 (AI 없이 규칙 기반 생성)",
                alternative_xpaths=[
                    f"//input[contains(@placeholder, {description_expr})]",
                    f"//input[contains(@name, {field_type_expr})]",
                ],
            )

        if any(word in desc_lower for word in ["링크", "link", "메뉴", "탭"]):
            link_text = description.replace("링크", "").replace("link", "").strip()
            if not link_text:
                link_text = description.strip()
            link_expr = self._xpath_text_expr(link_text)
            href_expr = self._xpath_text_expr(link_text.lower())
            return XPathSuggestion(
                xpath=f"//a[contains(text(), {link_expr})]",
                confidence=0.5,
                explanation="텍스트 기반 링크 XPath (AI 없이 규칙 기반 생성)",
                alternative_xpaths=[
                    f"//*[contains(@href, {href_expr})]",
                ],
            )

        description_expr = self._xpath_text_expr(description)
        return XPathSuggestion(
            xpath=f"//*[contains(text(), {description_expr})]",
            confidence=0.3,
            explanation="일반 텍스트 검색 XPath (AI 없이 규칙 기반 생성)",
            alternative_xpaths=[],
        )

    def analyze_page_elements(
        self,
        page_html: str,
        target_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        페이지 분석 후 주요 요소 자동 인식
        """
        client = self._get_client()
        if not client:
            return []

        target_types = target_types or ["button", "input", "link", "form"]

        system_prompt = """웹 페이지 HTML을 분석하여 자동화에 중요한 요소들을 식별합니다.

응답 형식 (JSON):
{
    "elements": [
        {
            "name": "요소 식별 이름 (영문, snake_case)",
            "xpath": "XPath",
            "type": "button|input|link|form|other",
            "description": "요소 설명",
            "confidence": 0.0-1.0
        }
    ]
}"""

        if self._page_context_allowed():
            safe_html = self._sanitize_external_context(page_html, max_chars=8000)
        else:
            safe_html = ""

        user_prompt = f"""다음 HTML에서 {', '.join(target_types)} 요소들을 분석해주세요.
중요한 상호작용 요소만 추출하고, 각각에 대해 안정적인 XPath를 생성해주세요.

HTML:
{safe_html}"""

        try:
            if self._provider == "gemini":
                return self._analyze_with_gemini(system_prompt, user_prompt)
            return self._analyze_with_openai(system_prompt, user_prompt)
        except Exception as e:
            logger.warning("페이지 분석 실패: %s", e)
            return []

    def _analyze_with_gemini(self, system_prompt: str, user_prompt: str) -> List[Dict[str, Any]]:
        """Gemini API로 페이지 분석 (google-genai)"""
        client = self._get_client()
        if client is None:
            return []
        client = cast(Any, client)
        try:
            config = self._build_gemini_generate_config(system_prompt)
            response = client.models.generate_content(
                model=self._model,
                contents=user_prompt,
                **({"config": config} if config is not None else {})
            )
            result = self._safe_json_loads(getattr(response, "text", None))
            elements = result.get("elements")
            return list(elements) if isinstance(elements, list) else []
        except Exception as e:
            logger.warning("Gemini Analyze Error: %s", e)
            return []

    def _analyze_with_openai(self, system_prompt: str, user_prompt: str) -> List[Dict[str, Any]]:
        """OpenAI API로 페이지 분석"""
        client = self._get_client()
        if client is None:
            return []
        client = cast(Any, client)
        response = client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=1500,
            response_format={"type": "json_object"},
        )
        result = self._safe_json_loads(self._extract_openai_content(response))
        elements = result.get("elements")
        return list(elements) if isinstance(elements, list) else []

    def improve_xpath(self, xpath: str, issue_description: Optional[str] = None) -> XPathSuggestion:
        """
        기존 XPath 개선 제안
        """
        client = self._get_client()
        if not client:
            return XPathSuggestion(
                xpath=xpath,
                confidence=0.0,
                explanation="AI가 비활성화되어 개선할 수 없습니다.",
                alternative_xpaths=[],
            )

        system_prompt = """XPath 전문가로서 주어진 XPath를 분석하고 개선합니다.

응답 형식 (JSON):
{
    "improved_xpath": "개선된 XPath",
    "confidence": 0.0-1.0,
    "explanation": "개선 내용 설명",
    "alternatives": ["대안 1", "대안 2"]
}"""

        user_prompt = f"XPath: {xpath}"
        if issue_description:
            user_prompt += f"\n문제: {issue_description}"

        try:
            if self._provider == "gemini":
                return self._improve_with_gemini(system_prompt, user_prompt, xpath)
            return self._improve_with_openai(system_prompt, user_prompt, xpath)
        except Exception as e:
            logger.warning("XPath 개선 실패: %s", e)
            return XPathSuggestion(
                xpath=xpath,
                confidence=0.0,
                explanation=f"개선 실패: {e}",
                alternative_xpaths=[],
            )

    def _improve_with_openai(
        self,
        system_prompt: str,
        user_prompt: str,
        original_xpath: str,
    ) -> XPathSuggestion:
        client = self._get_client()
        if client is None:
            return XPathSuggestion(
                xpath=original_xpath,
                confidence=0.0,
                explanation="OpenAI client unavailable",
                alternative_xpaths=[],
            )
        client = cast(Any, client)
        response = client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=400,
            response_format={"type": "json_object"},
        )
        result = self._safe_json_loads(self._extract_openai_content(response))
        return self._build_xpath_suggestion(
            result,
            xpath_key="improved_xpath",
            fallback_xpath=original_xpath,
            fallback_explanation="OpenAI 응답을 해석하지 못해 원본 XPath를 유지합니다.",
            confidence_default=0.5,
        )

    def _improve_with_gemini(
        self,
        system_prompt: str,
        user_prompt: str,
        original_xpath: str,
    ) -> XPathSuggestion:
        """Gemini를 사용한 XPath 개선"""
        client = self._get_client()
        if client is None:
            return XPathSuggestion(
                xpath=original_xpath,
                confidence=0.0,
                explanation="Gemini client unavailable",
                alternative_xpaths=[],
            )
        client = cast(Any, client)
        try:
            config = self._build_gemini_generate_config(system_prompt)
            response = client.models.generate_content(
                model=self._model,
                contents=user_prompt,
                **({"config": config} if config is not None else {})
            )
            result = self._safe_json_loads(getattr(response, "text", None))
            return self._build_xpath_suggestion(
                result,
                xpath_key="improved_xpath",
                fallback_xpath=original_xpath,
                fallback_explanation="Gemini 응답을 해석하지 못해 원본 XPath를 유지합니다.",
                confidence_default=0.5,
            )
        except Exception as e:
            return XPathSuggestion(
                xpath=original_xpath,
                confidence=0.0,
                explanation=f"Gemini 개선 실패: {e}",
                alternative_xpaths=[],
            )


if __name__ == "__main__":
    assistant = XPathAIAssistant()

    print(f"AI Available: {assistant.is_available()}")

    result = assistant.generate_xpath_from_description("로그인 버튼")
    print("\n=== '로그인 버튼' 제안 ===")
    print(f"XPath: {result.xpath}")
    print(f"Confidence: {result.confidence}")
    print(f"Explanation: {result.explanation}")
    print(f"Alternatives: {result.alternative_xpaths}")

    result = assistant.generate_xpath_from_description("이메일 입력창")
    print("\n=== '이메일 입력창' 제안 ===")
    print(f"XPath: {result.xpath}")
