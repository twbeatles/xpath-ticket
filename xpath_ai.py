# -*- coding: utf-8 -*-
"""
XPath Explorer AI Assistant v4.0
AI 기반 XPath 추천 모듈 (OpenAI API 통합)
"""

from typing import List, Dict, Optional
from dataclasses import dataclass
import json
import re
import os
from pathlib import Path


@dataclass
class XPathSuggestion:
    """AI가 제안한 XPath"""
    xpath: str
    confidence: float  # 0.0 - 1.0
    explanation: str
    alternative_xpaths: List[str]


class XPathAIAssistant:
    """AI 기반 XPath 추천 어시스턴트"""
    
    def __init__(self, api_key: str = None):
        """
        Args:
            api_key: OpenAI API 키 (없으면 환경변수 또는 설정 파일에서 로드)
        """
        self._api_key = api_key or self._load_api_key()
        self._client = None
        self._provider = "openai"  # "openai" or "gemini"
        self._config = self._load_config()
        self._api_key = api_key or self._config.get(f'{self._provider}_api_key')
        self._model = "gpt-4o-mini"
        
        # 설정 로드 시 이전 설정 확인
        if self._config.get('provider'):
            self._provider = self._config.get('provider')
            self._model = self._config.get('model', self._model)
            if not api_key:
                self._api_key = self._config.get(f'{self._provider}_api_key')
        
    def _load_config(self) -> Dict:
        """설정 로드"""
        config = {}
        
        # 1. 환경변수 확인
        openai_key = os.environ.get('OPENAI_API_KEY')
        gemini_key = os.environ.get('GEMINI_API_KEY') # or GOOGLE_API_KEY
        
        if openai_key: config['openai_api_key'] = openai_key
        if gemini_key: config['gemini_api_key'] = gemini_key
        
        # 2. 파일 확인
        config_path = Path.home() / '.xpath_explorer' / 'ai_config.json'
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    file_config = json.load(f)
                    config.update(file_config)
            except Exception:
                pass
                
        return config

    def _load_api_key(self) -> Optional[str]:
        """Deprecated: Use _load_config instead"""
        return self._config.get(f'{self._provider}_api_key')
    
    def configure(self, api_key: str, model: str = None, provider: str = "openai"):
        """
        AI 설정
        
        Args:
            api_key: API 키
            model: 사용할 모델
            provider: 'openai' or 'gemini'
        """
        self._provider = provider
        self._api_key = api_key
        
        if model:
            self._model = model
        else:
            # 기본 모델 설정
            self._model = "gpt-4o-mini" if provider == "openai" else "gemini-1.5-flash"
            
        self._client = None  # 재초기화
        
        # 설정 업데이트 및 저장
        self._config['provider'] = provider
        self._config['model'] = self._model
        self._config[f'{provider}_api_key'] = api_key
        
        self._save_config()

    def _save_config(self):
        config_path = Path.home() / '.xpath_explorer' / 'ai_config.json'
        config_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(config_path, 'w') as f:
                json.dump(self._config, f)
        except Exception:
            pass
    
    def is_available(self) -> bool:
        """AI 기능 사용 가능 여부"""
        return bool(self._api_key)
    
    def _get_client(self):
        """클라이언트 초기화 (Provider 분기)"""
        if self._client is not None:
            return self._client
            
        if not self._api_key:
            return None

        if self._provider == "openai":
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self._api_key)
            except ImportError:
                raise ImportError("OpenAI 라이브러리가 필요합니다. pip install openai")
                
        elif self._provider == "gemini":
            try:
                import google.generativeai as genai
                genai.configure(api_key=self._api_key)
                self._client = genai
            except ImportError:
                raise ImportError("Google Generative AI 라이브러리가 필요합니다. pip install google-generativeai")
                
        return self._client
    
    def generate_xpath_from_description(
        self, 
        description: str, 
        page_context: str = None,
        existing_xpaths: List[str] = None
    ) -> XPathSuggestion:
        """
        자연어 설명으로 XPath 생성
        
        Args:
            description: 요소에 대한 자연어 설명 (예: "로그인 버튼", "이메일 입력창")
            page_context: 페이지 HTML 일부 (선택)
            existing_xpaths: 이미 저장된 XPath 목록 (중복 방지용)
        
        Returns:
            XPathSuggestion 객체
        """
        client = self._get_client()
        if not client:
            return self._fallback_suggestion(description)
        
        # 프롬프트 구성
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
            user_prompt += f"\n\n페이지 컨텍스트:\n{page_context[:2000]}"
        
        if existing_xpaths:
            user_prompt += f"\n\n이미 존재하는 XPath (중복 방지):\n" + "\n".join(existing_xpaths[:10])
        
        try:
            if self._provider == "gemini":
                return self._generate_with_gemini(system_prompt, user_prompt)
            else:
                return self._generate_with_openai(system_prompt, user_prompt)
            
        except Exception as e:
            print(f"AI 요청 실패: {e}")
            return self._fallback_suggestion(description)
    
    def _generate_with_gemini(self, system_prompt: str, user_prompt: str) -> XPathSuggestion:
        """Gemini API 사용하여 생성"""
        client = self._get_client()
        import google.generativeai as genai
        
        model = client.GenerativeModel(
            self._model,
            system_instruction=system_prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json"
            )
        )
        
        try:
            response = model.generate_content(user_prompt)
            result = json.loads(response.text)
            
            return XPathSuggestion(
                xpath=result.get("xpath", ""),
                confidence=float(result.get("confidence", 0.0)),
                explanation=result.get("explanation", ""),
                alternative_xpaths=result.get("alternatives", [])
            )
        except Exception as e:
            # Fallback
            return XPathSuggestion(
                xpath=f"//error[contains(text(), '{str(e)}')]",
                confidence=0.0,
                explanation=f"AI 오류: {e}",
                alternative_xpaths=[]
            )

    def _generate_with_openai(self, system_prompt: str, user_prompt: str) -> XPathSuggestion:
        """OpenAI API 사용하여 생성"""
        client = self._get_client()
        response = client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=500,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        
        return XPathSuggestion(
            xpath=result.get("xpath", ""),
            confidence=float(result.get("confidence", 0.0)),
            explanation=result.get("explanation", ""),
            alternative_xpaths=result.get("alternatives", [])
        )
    
    def _fallback_suggestion(self, description: str) -> XPathSuggestion:
        """AI 없이 기본 XPath 제안 (규칙 기반)"""
        desc_lower = description.lower()
        
        # 버튼 패턴
        if any(word in desc_lower for word in ['버튼', 'button', 'btn', '클릭']):
            button_text = description.replace('버튼', '').replace('button', '').strip()
            return XPathSuggestion(
                xpath=f'//button[contains(text(), "{button_text}")]',
                confidence=0.6,
                explanation="텍스트 기반 버튼 XPath (AI 없이 규칙 기반 생성)",
                alternative_xpaths=[
                    f'//*[contains(@class, "btn")][contains(text(), "{button_text}")]',
                    f'//input[@type="submit"][@value="{button_text}"]'
                ]
            )
        
        # 입력 필드 패턴
        if any(word in desc_lower for word in ['입력', 'input', '필드', '텍스트박스']):
            field_type = "text"
            if '이메일' in desc_lower or 'email' in desc_lower:
                field_type = "email"
            elif '비밀번호' in desc_lower or 'password' in desc_lower:
                field_type = "password"
            
            return XPathSuggestion(
                xpath=f'//input[@type="{field_type}"]',
                confidence=0.5,
                explanation=f"{field_type} 타입 입력 필드 (AI 없이 규칙 기반 생성)",
                alternative_xpaths=[
                    f'//input[contains(@placeholder, "{description}")]',
                    f'//input[contains(@name, "{field_type}")]'
                ]
            )
        
        # 링크 패턴
        if any(word in desc_lower for word in ['링크', 'link', '메뉴', '탭']):
            link_text = description.replace('링크', '').replace('link', '').strip()
            return XPathSuggestion(
                xpath=f'//a[contains(text(), "{link_text}")]',
                confidence=0.5,
                explanation="텍스트 기반 링크 XPath (AI 없이 규칙 기반 생성)",
                alternative_xpaths=[
                    f'//*[contains(@href, "{link_text.lower()}")]'
                ]
            )
        
        # 기본 (텍스트 기반)
        return XPathSuggestion(
            xpath=f'//*[contains(text(), "{description}")]',
            confidence=0.3,
            explanation="일반 텍스트 검색 XPath (AI 없이 규칙 기반 생성)",
            alternative_xpaths=[]
        )
    
    def analyze_page_elements(self, page_html: str, target_types: List[str] = None) -> List[Dict]:
        """
        페이지 분석 후 주요 요소 자동 인식
        
        Args:
            page_html: 페이지 HTML
            target_types: 찾을 요소 타입 ["button", "input", "link", "form"]
        
        Returns:
            [{name, xpath, type, confidence}, ...]
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

        user_prompt = f"""다음 HTML에서 {', '.join(target_types)} 요소들을 분석해주세요.
중요한 상호작용 요소만 추출하고, 각각에 대해 안정적인 XPath를 생성해주세요.

HTML:
{page_html[:8000]}"""

        try:
            response = client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                max_tokens=1500,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            return result.get("elements", [])
            
        except Exception as e:
            print(f"페이지 분석 실패: {e}")
            return []
    
    def improve_xpath(self, xpath: str, issue_description: str = None) -> XPathSuggestion:
        """
        기존 XPath 개선 제안
        
        Args:
            xpath: 개선할 XPath
            issue_description: 문제 설명 (예: "요소를 찾지 못함", "너무 많은 요소가 매칭됨")
        """
        client = self._get_client()
        if not client:
            return XPathSuggestion(
                xpath=xpath,
                confidence=0.0,
                explanation="AI가 비활성화되어 개선할 수 없습니다.",
                alternative_xpaths=[]
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
            response = client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=400,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            return XPathSuggestion(
                xpath=result.get("improved_xpath", xpath),
                confidence=float(result.get("confidence", 0.5)),
                explanation=result.get("explanation", ""),
                alternative_xpaths=result.get("alternatives", [])
            )
            
        except Exception as e:
            print(f"XPath 개선 실패: {e}")
            return XPathSuggestion(
                xpath=xpath,
                confidence=0.0,
                explanation=f"개선 실패: {e}",
                alternative_xpaths=[]
            )


# 테스트용
if __name__ == "__main__":
    assistant = XPathAIAssistant()
    
    print(f"AI Available: {assistant.is_available()}")
    
    # Fallback 테스트
    result = assistant.generate_xpath_from_description("로그인 버튼")
    print(f"\n=== '로그인 버튼' 제안 ===")
    print(f"XPath: {result.xpath}")
    print(f"Confidence: {result.confidence}")
    print(f"Explanation: {result.explanation}")
    print(f"Alternatives: {result.alternative_xpaths}")
    
    result = assistant.generate_xpath_from_description("이메일 입력창")
    print(f"\n=== '이메일 입력창' 제안 ===")
    print(f"XPath: {result.xpath}")
