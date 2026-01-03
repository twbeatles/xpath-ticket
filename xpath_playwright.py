# -*- coding: utf-8 -*-
"""
XPath Explorer - Playwright Browser Manager
Playwright 기반 브라우저 관리 및 자동 탐색 기능
탐지 우회 기술 포함
"""

import logging
import random
import json
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass, field
from dataclasses import dataclass, field
from pathlib import Path

# 상수 임포트
from xpath_constants import USER_AGENTS, STEALTH_SCRIPT, SCAN_SELECTORS

logger = logging.getLogger('XPathExplorer')

# Playwright 가용성 확인
try:
    from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext
    from playwright.sync_api import TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright 모듈이 설치되지 않았습니다. pip install playwright && playwright install")


@dataclass
class ScannedElement:
    """스캔된 요소 정보"""
    xpath: str
    css_selector: str
    tag: str
    text: str
    element_id: str
    element_name: str
    element_class: str
    is_visible: bool
    is_enabled: bool
    frame_path: str = ""


@dataclass
class NetworkRequest:
    """네트워크 요청 정보"""
    url: str
    method: str
    resource_type: str
    status: int = 0
    response_body: str = ""


class PlaywrightManager:
    """Playwright 기반 브라우저 관리 (탐지 우회 포함)"""
    
    def __init__(self):
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._is_initialized = False
        self._stealth_enabled = False
        self._network_requests: List[NetworkRequest] = []
        self._network_monitoring = False
        
    @property
    def is_available(self) -> bool:
        """Playwright 사용 가능 여부"""
        return PLAYWRIGHT_AVAILABLE
    
    @property
    def page(self) -> Optional[Page]:
        """현재 페이지 객체"""
        return self._page
    
    def launch(self, headless: bool = False, stealth: bool = True) -> bool:
        """
        브라우저 실행 (탐지 우회 옵션)
        
        Args:
            headless: 헤드리스 모드
            stealth: 탐지 우회 활성화
        """
        if not PLAYWRIGHT_AVAILABLE:
            logger.error("Playwright가 설치되지 않았습니다.")
            return False
            
        try:
            # 랜덤 User-Agent 선택
            user_agent = random.choice(USER_AGENTS)
            
            self._playwright = sync_playwright().start()
            
            # 브라우저 시작 옵션
            launch_args = [
                '--start-maximized',
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-infobars',
                '--disable-extensions',
                '--lang=ko-KR',
            ]
            
            if headless:
                launch_args.extend([
                    '--headless=new',  # 새로운 headless 모드 (탐지 어려움)
                ])
            
            self._browser = self._playwright.chromium.launch(
                headless=headless,
                args=launch_args
            )
            
            # 컨텍스트 생성 (fingerprint 설정)
            self._context = self._browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent=user_agent,
                locale='ko-KR',
                timezone_id='Asia/Seoul',
                geolocation={'latitude': 37.5665, 'longitude': 126.9780},
                permissions=['geolocation'],
                color_scheme='light',
                device_scale_factor=1,
            )
            
            self._page = self._context.new_page()
            
            # 탐지 우회 스크립트 주입
            if stealth:
                self._apply_stealth()
            
            self._is_initialized = True
            self._stealth_enabled = stealth
            logger.info(f"Playwright 브라우저 실행 완료 (stealth={stealth})")
            return True
            
        except Exception as e:
            logger.error(f"Playwright 브라우저 실행 실패: {e}")
            return False
    
    def _apply_stealth(self):
        """탐지 우회 스크립트 적용"""
        if self._page:
            # 모든 페이지 로드 전에 스크립트 주입
            self._page.add_init_script(STEALTH_SCRIPT)
            logger.debug("Stealth 스크립트 적용됨")
    
    def close(self):
        """브라우저 종료"""
        try:
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception as e:
            logger.debug(f"Playwright 종료 중 예외: {e}")
        finally:
            self._page = None
            self._context = None
            self._browser = None
            self._playwright = None
            self._is_initialized = False
            self._network_requests = []
    
    def is_alive(self) -> bool:
        """연결 상태 확인"""
        if not self._is_initialized or not self._page:
            return False
        try:
            self._page.evaluate("() => true")
            return True
        except Exception:
            return False
    
    def navigate(self, url: str, timeout: int = 30000, 
                 wait_until: str = 'domcontentloaded') -> bool:
        """URL 이동"""
        if not self.is_alive():
            return False
        try:
            self._page.goto(url, timeout=timeout, wait_until=wait_until)
            return True
        except PlaywrightTimeout:
            logger.warning(f"페이지 로딩 타임아웃: {url}")
            return True
        except Exception as e:
            logger.error(f"페이지 이동 실패: {e}")
            return False
    
    def get_current_url(self) -> str:
        """현재 URL 반환"""
        if self._page:
            return self._page.url
        return ""
    
    def get_page_title(self) -> str:
        """현재 페이지 제목"""
        if self._page:
            return self._page.title()
        return ""
    
    # =========================================================================
    # 네트워크 모니터링
    # =========================================================================
    
    def start_network_monitoring(self, filter_types: List[str] = None):
        """네트워크 요청 모니터링 시작"""
        if not self.is_alive():
            return
            
        self._network_requests = []
        self._network_monitoring = True
        filter_types = filter_types or ['xhr', 'fetch', 'document']
        
        def on_request(request):
            if request.resource_type in filter_types:
                self._network_requests.append(NetworkRequest(
                    url=request.url,
                    method=request.method,
                    resource_type=request.resource_type
                ))
        
        def on_response(response):
            for req in self._network_requests:
                if req.url == response.url:
                    req.status = response.status
                    break
        
        self._page.on('request', on_request)
        self._page.on('response', on_response)
        logger.info("네트워크 모니터링 시작")
    
    def stop_network_monitoring(self) -> List[NetworkRequest]:
        """네트워크 모니터링 중지 및 결과 반환"""
        self._network_monitoring = False
        return self._network_requests.copy()
    
    def get_network_requests(self) -> List[NetworkRequest]:
        """현재까지의 네트워크 요청 목록"""
        return self._network_requests.copy()
    
    # =========================================================================
    # 쿠키 관리
    # =========================================================================
    
    def get_cookies(self) -> List[Dict]:
        """모든 쿠키 가져오기"""
        if not self._context:
            return []
        return self._context.cookies()
    
    def set_cookies(self, cookies: List[Dict]):
        """쿠키 설정"""
        if self._context:
            self._context.add_cookies(cookies)
    
    def save_cookies(self, filepath: str):
        """쿠키를 파일로 저장"""
        cookies = self.get_cookies()
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(cookies, f, indent=2, ensure_ascii=False)
        logger.info(f"쿠키 저장됨: {filepath}")
    
    def load_cookies(self, filepath: str) -> bool:
        """파일에서 쿠키 로드"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
            self.set_cookies(cookies)
            logger.info(f"쿠키 로드됨: {filepath}")
            return True
        except Exception as e:
            logger.error(f"쿠키 로드 실패: {e}")
            return False
    
    def clear_cookies(self):
        """모든 쿠키 삭제"""
        if self._context:
            self._context.clear_cookies()
    
    # =========================================================================
    # 로컬 스토리지
    # =========================================================================
    
    def get_local_storage(self) -> Dict:
        """로컬 스토리지 가져오기"""
        if not self.is_alive():
            return {}
        try:
            return self._page.evaluate("() => Object.assign({}, localStorage)")
        except Exception:
            return {}
    
    def set_local_storage(self, data: Dict):
        """로컬 스토리지 설정"""
        if not self.is_alive():
            return
        for key, value in data.items():
            self._page.evaluate(f"localStorage.setItem('{key}', '{value}')")
    
    # =========================================================================
    # 자동 탐색 기능
    # =========================================================================
    
    def scan_elements(self, element_type: str = 'interactive', 
                      max_count: int = 100) -> List[ScannedElement]:
        """페이지 요소 자동 스캔"""
        if not self.is_alive():
            return []
            
        selector = SCAN_SELECTORS.get(element_type, SCAN_SELECTORS['interactive'])
        results = []
        
        try:
            elements = self._page.query_selector_all(selector)
            
            for i, el in enumerate(elements[:max_count]):
                try:
                    tag = el.evaluate("el => el.tagName.toLowerCase()")
                    text = el.inner_text()[:100] if el.inner_text() else ""
                    el_id = el.get_attribute('id') or ""
                    el_name = el.get_attribute('name') or ""
                    el_class = el.get_attribute('class') or ""
                    is_visible = el.is_visible()
                    is_enabled = el.is_enabled()
                    
                    xpath = self._generate_xpath(el, el_id, el_name, tag, text)
                    css = self._generate_css_selector(el_id, el_name, el_class, tag)
                    
                    results.append(ScannedElement(
                        xpath=xpath,
                        css_selector=css,
                        tag=tag,
                        text=text.strip()[:50],
                        element_id=el_id,
                        element_name=el_name,
                        element_class=el_class[:50],
                        is_visible=is_visible,
                        is_enabled=is_enabled
                    ))
                except Exception as e:
                    logger.debug(f"요소 스캔 중 오류: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"요소 스캔 실패: {e}")
            
        return results
    
    def _generate_xpath(self, el, el_id: str, el_name: str, 
                        tag: str, text: str) -> str:
        """최적화된 XPath 생성"""
        if el_id:
            return f'//*[@id="{el_id}"]'
        if el_name:
            return f'//{tag}[@name="{el_name}"]'
        if text and tag in ['button', 'a']:
            clean_text = text.strip()[:30]
            if clean_text:
                return f'//{tag}[contains(text(), "{clean_text}")]'
        
        try:
            full_xpath = el.evaluate("""el => {
                if (el.id) return '//*[@id="' + el.id + '"]';
                var path = [];
                while (el.nodeType === Node.ELEMENT_NODE) {
                    var selector = el.nodeName.toLowerCase();
                    if (el.id) {
                        selector = '*[@id="' + el.id + '"]';
                        path.unshift('//' + selector);
                        break;
                    } else {
                        var sib = el, nth = 1;
                        while (sib = sib.previousElementSibling) {
                            if (sib.nodeName.toLowerCase() === selector) nth++;
                        }
                        if (nth !== 1) selector += '[' + nth + ']';
                    }
                    path.unshift(selector);
                    el = el.parentNode;
                }
                return '/' + path.join('/');
            }""")
            return full_xpath
        except Exception:
            return f"//{tag}"
    
    def _generate_css_selector(self, el_id: str, el_name: str, 
                                el_class: str, tag: str) -> str:
        """CSS 셀렉터 생성"""
        if el_id:
            return f"#{el_id}"
        if el_name:
            return f'{tag}[name="{el_name}"]'
        if el_class:
            classes = el_class.split()[:2]
            return f"{tag}.{'.'.join(classes)}"
        return tag
    
    def highlight(self, xpath: str, duration_ms: int = 2000) -> bool:
        """요소 하이라이트"""
        if not self.is_alive():
            return False
            
        try:
            el = self._page.query_selector(f"xpath={xpath}")
            if not el:
                return False
                
            el.evaluate(f"""el => {{
                const original = {{
                    outline: el.style.outline,
                    outlineOffset: el.style.outlineOffset,
                    backgroundColor: el.style.backgroundColor
                }};
                el.style.outline = '3px solid #00ff88';
                el.style.outlineOffset = '2px';
                el.style.backgroundColor = 'rgba(0, 255, 136, 0.2)';
                el.scrollIntoView({{behavior: 'smooth', block: 'center'}});
                setTimeout(() => {{
                    el.style.outline = original.outline;
                    el.style.outlineOffset = original.outlineOffset;
                    el.style.backgroundColor = original.backgroundColor;
                }}, {duration_ms});
            }}""")
            return True
        except Exception as e:
            logger.error(f"하이라이트 실패: {e}")
            return False
    
    def validate_xpath(self, xpath: str) -> Dict:
        """XPath 검증"""
        if not self.is_alive():
            return {"found": False, "msg": "브라우저 연결 안됨"}
            
        try:
            elements = self._page.query_selector_all(f"xpath={xpath}")
            
            if elements:
                first = elements[0]
                tag = first.evaluate("el => el.tagName.toLowerCase()")
                text = first.inner_text()[:50] if first.inner_text() else ""
                
                return {
                    "found": True,
                    "count": len(elements),
                    "tag": tag,
                    "text": text,
                    "visible": first.is_visible()
                }
            else:
                return {"found": False, "msg": "요소를 찾을 수 없음"}
                
        except Exception as e:
            return {"found": False, "msg": str(e)}
    
    # =========================================================================
    # 요소 조작
    # =========================================================================
    
    def click_element(self, xpath: str, timeout: int = 5000) -> bool:
        """요소 클릭"""
        if not self.is_alive():
            return False
        try:
            self._page.click(f"xpath={xpath}", timeout=timeout)
            return True
        except Exception as e:
            logger.error(f"클릭 실패: {e}")
            return False
    
    def fill_input(self, xpath: str, text: str, clear_first: bool = True) -> bool:
        """입력 필드에 텍스트 입력"""
        if not self.is_alive():
            return False
        try:
            if clear_first:
                self._page.fill(f"xpath={xpath}", text)
            else:
                self._page.type(f"xpath={xpath}", text)
            return True
        except Exception as e:
            logger.error(f"입력 실패: {e}")
            return False
    
    def wait_for_element(self, xpath: str, timeout: int = 10000, 
                         state: str = 'visible') -> bool:
        """요소 대기"""
        if not self.is_alive():
            return False
        try:
            self._page.wait_for_selector(f"xpath={xpath}", 
                                         timeout=timeout, state=state)
            return True
        except Exception as e:
            logger.debug(f"요소 대기 실패: {e}")
            return False
    
    def wait_for_navigation(self, timeout: int = 30000) -> bool:
        """페이지 이동 대기"""
        if not self.is_alive():
            return False
        try:
            self._page.wait_for_load_state('domcontentloaded', timeout=timeout)
            return True
        except Exception:
            return False
    
    # =========================================================================
    # 스크린샷 및 캡처
    # =========================================================================
    
    def screenshot(self, path: str = None, full_page: bool = False) -> Optional[bytes]:
        """스크린샷 캡처"""
        if not self.is_alive():
            return None
        try:
            if path:
                return self._page.screenshot(path=path, full_page=full_page)
            return self._page.screenshot(full_page=full_page)
        except Exception as e:
            logger.error(f"스크린샷 실패: {e}")
            return None
    
    def capture_element(self, xpath: str, path: str = None) -> Optional[bytes]:
        """특정 요소 캡처"""
        if not self.is_alive():
            return None
        try:
            el = self._page.query_selector(f"xpath={xpath}")
            if el:
                if path:
                    return el.screenshot(path=path)
                return el.screenshot()
        except Exception as e:
            logger.error(f"요소 캡처 실패: {e}")
        return None

    
    def save_pdf(self, path: str) -> bool:
        """페이지 PDF 저장"""
        if not self.is_alive():
            return False
        try:
            self._page.pdf(path=path)
            return True
        except Exception as e:
            logger.error(f"PDF 저장 실패: {e}")
            return False
    
    # =========================================================================
    # iframe 처리
    # =========================================================================
    
    def get_frames(self) -> List[Dict]:
        """모든 프레임 목록"""
        if not self.is_alive():
            return []
            
        frames = []
        for frame in self._page.frames:
            frames.append({
                "name": frame.name or "(unnamed)",
                "url": frame.url,
                "is_main": frame == self._page.main_frame
            })
        return frames
    
    def switch_to_frame(self, frame_name: str) -> bool:
        """특정 프레임으로 전환"""
        return True
    
    # =========================================================================
    # JavaScript 실행
    # =========================================================================
    
    def execute_script(self, script: str) -> Any:
        """JavaScript 실행"""
        if not self.is_alive():
            return None
        try:
            return self._page.evaluate(script)
        except Exception as e:
            logger.error(f"스크립트 실행 실패: {e}")
            return None
    
    def inject_script(self, script: str):
        """페이지 로드 시 스크립트 주입"""
        if self._page:
            self._page.add_init_script(script)

