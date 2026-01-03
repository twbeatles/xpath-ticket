# -*- coding: utf-8 -*-
"""
XPath Explorer Playwright Integration
네트워크 분석 및 자동 탐색 모듈
"""

import asyncio
import json
import time
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
import threading


@dataclass
class RequestInfo:
    """네트워크 요청 정보"""
    url: str
    method: str
    resource_type: str  # document, xhr, fetch, script, image, etc.
    headers: Dict = field(default_factory=dict)
    post_data: str = ""
    timestamp: str = ""
    
    # 응답 정보
    status: int = 0
    status_text: str = ""
    response_headers: Dict = field(default_factory=dict)
    response_size: int = 0
    response_time_ms: float = 0.0


class NetworkAnalyzer:
    """
    Playwright 기반 네트워크 분석기
    
    네트워크 요청/응답을 가로채서 분석합니다.
    """
    
    def __init__(self):
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        
        self._requests: List[RequestInfo] = []
        self._is_capturing = False
        self._capture_start_time = None
        
        # 필터 설정
        self.filter_types: List[str] = []  # 빈 리스트면 모든 타입 캡처
        self.filter_url_pattern: str = ""
    
    def is_playwright_available(self) -> bool:
        """Playwright 사용 가능 여부 확인"""
        try:
            from playwright.sync_api import sync_playwright
            return True
        except ImportError:
            return False
    
    def start_browser(self, url: str = "about:blank", headless: bool = False) -> bool:
        """
        브라우저 시작 및 네트워크 캡처 준비
        
        Args:
            url: 초기 URL
            headless: 헤드리스 모드 여부
        """
        if not self.is_playwright_available():
            print("Playwright가 설치되지 않았습니다. pip install playwright 후 playwright install 실행")
            return False
        
        try:
            from playwright.sync_api import sync_playwright
            
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=headless)
            self._context = self._browser.new_context()
            self._page = self._context.new_page()
            
            # 네트워크 이벤트 핸들러 등록
            self._page.on("request", self._on_request)
            self._page.on("response", self._on_response)
            
            self._page.goto(url)
            return True
            
        except Exception as e:
            print(f"브라우저 시작 실패: {e}")
            return False
    
    def close(self):
        """브라우저 종료"""
        try:
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except:
            pass
        finally:
            self._browser = None
            self._playwright = None
            self._page = None
    
    def start_capture(self):
        """네트워크 캡처 시작"""
        self._requests.clear()
        self._is_capturing = True
        self._capture_start_time = time.time()
    
    def stop_capture(self) -> List[RequestInfo]:
        """네트워크 캡처 중지 및 결과 반환"""
        self._is_capturing = False
        return self._requests.copy()
    
    def is_capturing(self) -> bool:
        """캡처 중인지 확인"""
        return self._is_capturing
    
    def _on_request(self, request):
        """요청 이벤트 핸들러"""
        if not self._is_capturing:
            return
        
        # 필터 적용
        resource_type = request.resource_type
        if self.filter_types and resource_type not in self.filter_types:
            return
        
        if self.filter_url_pattern and self.filter_url_pattern not in request.url:
            return
        
        req_info = RequestInfo(
            url=request.url,
            method=request.method,
            resource_type=resource_type,
            headers=dict(request.headers),
            post_data=request.post_data or "",
            timestamp=datetime.now().isoformat()
        )
        
        self._requests.append(req_info)
    
    def _on_response(self, response):
        """응답 이벤트 핸들러"""
        if not self._is_capturing:
            return
        
        # 해당 요청 찾기
        for req in reversed(self._requests):
            if req.url == response.url and req.status == 0:
                req.status = response.status
                req.status_text = response.status_text
                req.response_headers = dict(response.headers)
                
                try:
                    # 응답 크기 (헤더에서)
                    content_length = response.headers.get('content-length', '0')
                    req.response_size = int(content_length)
                except:
                    pass
                
                break
    
    def navigate(self, url: str):
        """URL 이동"""
        if self._page:
            self._page.goto(url)
    
    def get_requests(self) -> List[RequestInfo]:
        """캡처된 요청 목록"""
        return self._requests.copy()
    
    def filter_requests(self, 
                       resource_type: str = None,
                       method: str = None,
                       url_contains: str = None,
                       status_code: int = None) -> List[RequestInfo]:
        """
        요청 필터링
        
        Args:
            resource_type: 리소스 타입 (xhr, fetch, document 등)
            method: HTTP 메서드 (GET, POST 등)
            url_contains: URL에 포함될 문자열
            status_code: HTTP 상태 코드
        """
        filtered = self._requests
        
        if resource_type:
            filtered = [r for r in filtered if r.resource_type == resource_type]
        if method:
            filtered = [r for r in filtered if r.method.upper() == method.upper()]
        if url_contains:
            filtered = [r for r in filtered if url_contains in r.url]
        if status_code:
            filtered = [r for r in filtered if r.status == status_code]
        
        return filtered
    
    def export_har(self, file_path: str):
        """
        HAR 형식으로 내보내기
        
        Args:
            file_path: 저장할 파일 경로
        """
        har = {
            "log": {
                "version": "1.2",
                "creator": {
                    "name": "XPath Explorer",
                    "version": "3.3"
                },
                "entries": []
            }
        }
        
        for req in self._requests:
            entry = {
                "startedDateTime": req.timestamp,
                "request": {
                    "method": req.method,
                    "url": req.url,
                    "headers": [{"name": k, "value": v} for k, v in req.headers.items()],
                    "postData": {"text": req.post_data} if req.post_data else {}
                },
                "response": {
                    "status": req.status,
                    "statusText": req.status_text,
                    "headers": [{"name": k, "value": v} for k, v in req.response_headers.items()],
                    "content": {
                        "size": req.response_size
                    }
                }
            }
            har["log"]["entries"].append(entry)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(har, f, ensure_ascii=False, indent=2)
    
    def export_json(self, file_path: str):
        """JSON 형식으로 내보내기"""
        data = [asdict(r) for r in self._requests]
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


class PlaywrightXPathExtractor:
    """
    Playwright 기반 XPath 자동 추출기
    
    페이지의 주요 요소들에서 XPath를 자동으로 추출합니다.
    """
    
    def __init__(self):
        self._playwright = None
        self._browser = None
        self._page = None
    
    def start(self, url: str, headless: bool = True) -> bool:
        """브라우저 시작"""
        try:
            from playwright.sync_api import sync_playwright
            
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=headless)
            self._page = self._browser.new_page()
            self._page.goto(url)
            return True
        except Exception as e:
            print(f"시작 실패: {e}")
            return False
    
    def close(self):
        """브라우저 종료"""
        try:
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except:
            pass
    
    def extract_interactive_elements(self) -> List[Dict]:
        """
        상호작용 가능한 요소 자동 추출
        
        버튼, 링크, 입력 필드 등을 자동으로 찾아 XPath 생성
        """
        if not self._page:
            return []
        
        # JavaScript로 요소 탐색
        script = '''
        () => {
            const elements = [];
            
            // 버튼
            document.querySelectorAll('button, input[type="button"], input[type="submit"]').forEach((el, idx) => {
                elements.push({
                    tag: el.tagName.toLowerCase(),
                    type: 'button',
                    text: el.textContent?.trim() || el.value || '',
                    id: el.id,
                    className: el.className,
                    name: el.name || ''
                });
            });
            
            // 링크
            document.querySelectorAll('a[href]').forEach((el, idx) => {
                elements.push({
                    tag: 'a',
                    type: 'link',
                    text: el.textContent?.trim() || '',
                    id: el.id,
                    className: el.className,
                    href: el.href
                });
            });
            
            // 입력 필드
            document.querySelectorAll('input[type="text"], input[type="password"], input[type="email"], textarea').forEach((el, idx) => {
                elements.push({
                    tag: el.tagName.toLowerCase(),
                    type: 'input',
                    placeholder: el.placeholder || '',
                    id: el.id,
                    className: el.className,
                    name: el.name || ''
                });
            });
            
            return elements;
        }
        '''
        
        try:
            raw_elements = self._page.evaluate(script)
            
            # XPath 생성
            results = []
            for elem in raw_elements:
                xpath = self._generate_xpath(elem)
                results.append({
                    'xpath': xpath,
                    'tag': elem.get('tag', ''),
                    'type': elem.get('type', ''),
                    'text': elem.get('text', '')[:50],
                    'id': elem.get('id', ''),
                    'name': elem.get('name', '')
                })
            
            return results
            
        except Exception as e:
            print(f"요소 추출 실패: {e}")
            return []
    
    def _generate_xpath(self, elem: Dict) -> str:
        """요소 정보로 XPath 생성"""
        tag = elem.get('tag', 'div')
        elem_id = elem.get('id', '')
        name = elem.get('name', '')
        text = elem.get('text', '')
        
        # ID가 있으면 가장 간단한 XPath
        if elem_id:
            return f"//*[@id='{elem_id}']"
        
        # name 속성
        if name:
            return f"//{tag}[@name='{name}']"
        
        # 텍스트 기반
        if text and len(text) < 30:
            safe_text = text.replace("'", "\\'")
            return f"//{tag}[contains(text(), '{safe_text}')]"
        
        # 기본
        return f"//{tag}"
    
    def find_element_xpath(self, selector: str) -> Optional[str]:
        """
        CSS 선택자로 요소를 찾고 XPath 반환
        
        Args:
            selector: CSS 선택자
        """
        if not self._page:
            return None
        
        try:
            # 요소가 존재하는지 확인
            element = self._page.locator(selector).first
            if element.count() == 0:
                return None
            
            # JavaScript로 XPath 생성
            xpath_script = '''
            (element) => {
                function getXPath(el) {
                    if (el.id) return `//*[@id="${el.id}"]`;
                    if (el === document.body) return '/html/body';
                    
                    let ix = 0;
                    const siblings = el.parentNode ? el.parentNode.childNodes : [];
                    for (let i = 0; i < siblings.length; i++) {
                        const sibling = siblings[i];
                        if (sibling === el) {
                            const path = getXPath(el.parentNode);
                            const tag = el.tagName.toLowerCase();
                            return `${path}/${tag}[${ix + 1}]`;
                        }
                        if (sibling.nodeType === 1 && sibling.tagName === el.tagName) {
                            ix++;
                        }
                    }
                    return '';
                }
                return getXPath(element);
            }
            '''
            
            return element.evaluate(xpath_script)
            
        except Exception as e:
            print(f"XPath 생성 실패: {e}")
            return None
