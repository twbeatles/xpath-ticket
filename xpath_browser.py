# -*- coding: utf-8 -*-
"""
XPath Explorer Browser Manager
"""

import time
import logging
from typing import List, Dict, Optional, Any, Tuple

from xpath_constants import PICKER_SCRIPT

# 로거 설정
logger = logging.getLogger('XPathExplorer')

# Selenium Imports
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import *
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    logger.error("Selenium 모듈이 설치되지 않았습니다.")

try:
    import undetected_chromedriver as uc
    UC_AVAILABLE = True
except ImportError:
    UC_AVAILABLE = False

try:
    from webdriver_manager.chrome import ChromeDriverManager
    WDM_AVAILABLE = True
except ImportError:
    WDM_AVAILABLE = False


class BrowserManager:
    """브라우저 관리"""
    
    def __init__(self):
        self.driver = None
        self.current_frame_path = ""  # 현재 활성 프레임 경로
        self.frame_cache = []  # 캐시된 프레임 목록
        self.frame_cache_time = 0  # 캐시 생성 시간
        self.FRAME_CACHE_DURATION = 2.0  # 캐시 유효 시간 (초)
    
    def create_driver(self, use_undetected: bool = True) -> bool:
        """드라이버 생성"""
        try:
            logger.info("브라우저 드라이버 생성 시작...")
            if use_undetected and UC_AVAILABLE:
                options = uc.ChromeOptions()
                options.add_argument('--start-maximized')
                options.add_argument('--disable-popup-blocking')
                options.add_argument('--lang=ko-KR')
                self.driver = uc.Chrome(options=options, use_subprocess=True)
                logger.info("Undetected Chrome 드라이버 생성 완료")
            else:
                options = Options()
                options.add_argument('--start-maximized')
                options.add_argument('--disable-popup-blocking')
                options.add_argument('--lang=ko-KR')
                options.add_argument('--disable-blink-features=AutomationControlled')
                options.add_experimental_option('excludeSwitches', ['enable-automation'])
                
                if WDM_AVAILABLE:
                    service = Service(ChromeDriverManager().install())
                    self.driver = webdriver.Chrome(service=service, options=options)
                else:
                    self.driver = webdriver.Chrome(options=options)
                logger.info("표준 Chrome 드라이버 생성 완료")
            
            return True
        except Exception as e:
            logger.error(f"드라이버 생성 실패: {e}")
            return False
            
    def close(self):
        """브라우저 닫기"""
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                logger.debug(f"드라이버 종료 중 오류 (무시됨): {e}")
                pass
            self.driver = None
            
    def is_alive(self) -> bool:
        """연결 상태 확인 - 현재 윈도우가 닫혀도 다른 윈도우로 자동 전환"""
        if not self.driver:
            return False
        try:
            # 현재 윈도우 핸들 확인 시도
            _ = self.driver.current_window_handle
            return True
        except NoSuchWindowException:
            logger.warning("현재 윈도우가 가 닫혔습니다. 다른 윈도우로 전환을 시도합니다.")
            return self._recover_to_available_window()
        except Exception as e:
            logger.error(f"브라우저 연결 확인 실패: {e}")
            return False
            
    def _recover_to_available_window(self) -> bool:
        """사용 가능한 다른 윈도우로 자동 복구"""
        try:
            handles = self.driver.window_handles
            if handles:
                self.driver.switch_to.window(handles[-1])  # 마지막(보통 최신) 윈도우로 전환
                logger.info(f"윈도우 복구 성공: {self.driver.title}")
                return True
            else:
                logger.error("사용 가능한 윈도우가 없습니다.")
                return False
        except Exception as e:
            logger.debug(f"윈도우 복구 중 오류: {e}")
            return False

    def ensure_valid_window(self):
        """유효한 윈도우 상태 보장 (외부에서 호출 가능)"""
        if not self.is_alive():
            raise Exception("브라우저가 연결되지 않았습니다.")
            
    def navigate(self, url: str):
        """URL 이동"""
        if self.is_alive():
            try:
                self.driver.get(url)
            except Exception as e:
                logger.error(f"이동 실패: {e}")

    # -------------------------------------------------------------------------
    # Frame 및 Element 관리
    # -------------------------------------------------------------------------

    def get_all_frames(self, max_depth: int = 5) -> List[tuple]:
        """모든 iframe을 재귀적으로 탐색 (인터파크 중첩 iframe 지원)"""
        self.ensure_valid_window()
        # 캐시 확인
        current_time = time.time()
        if (self.frame_cache and 
            current_time - self.frame_cache_time < self.FRAME_CACHE_DURATION):
            return self.frame_cache.copy()
            
        frames_list = []
        original_handle = self.driver.current_window_handle
        
        try:
            # 메인 컨텐츠로 초기화
            self.driver.switch_to.default_content()
            self._scan_frames(frames_list, "", 0, max_depth)
            
            # 캐시 업데이트
            self.frame_cache = frames_list.copy()
            self.frame_cache_time = current_time
            
        except Exception as e:
            logger.error(f"프레임 스캔 중 오류: {e}")
            # 오류 발생 시 캐시 초기화
            self.frame_cache = []
            self.frame_cache_time = 0
        finally:
            # 복구
            try:
                self.driver.switch_to.window(original_handle)
                self.driver.switch_to.default_content()
            except Exception as e:
                logger.debug(f"프레임 복구 중 오류: {e}")
                pass
                
        return frames_list

    def _scan_frames(self, results_list, parent_path: str = "", depth: int = 0, max_depth: int = 5):
        if depth > max_depth:
            return

        # 현재 컨텍스트의 모든 iframe 찾기
        try:
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
        except Exception:
            return  # iframe 검색 실패

        for i, frame in enumerate(iframes):
            try:
                # 프레임 식별자 (ID > Name > Index)
                frame_id = frame.get_attribute("id")
                frame_name = frame.get_attribute("name")
                
                identifier = frame_id if frame_id else (frame_name if frame_name else f"index={i}")
                
                # 경로 구성
                current_path = f"{parent_path}/{identifier}" if parent_path else identifier
                
                # 결과에 추가
                results_list.append((current_path, identifier))
                
                # 해당 프레임으로 전환하여 재귀 탐색
                self.driver.switch_to.frame(frame)
                self._scan_frames(results_list, current_path, depth + 1, max_depth)
                
                # 상위로 복귀
                self.driver.switch_to.parent_frame()
                
            except StaleElementReferenceException:
                # 프레임이 DOM에서 사라짐
                continue
            except Exception as e:
                logger.debug(f"프레임 내부 스캔 실패 ({identifier}): {e}")
                try:
                    self.driver.switch_to.parent_frame()
                except Exception as e:
                    logger.debug(f"부모 프레임 복귀 실패: {e}")
                    pass

    def switch_to_frame_by_path(self, frame_path: str) -> bool:
        """프레임 경로로 전환 (예: 'ifrmSeat/ifrmSeatDetail')"""
        self.ensure_valid_window()
        
        if not frame_path or frame_path == "main":
            self.driver.switch_to.default_content()
            self.current_frame_path = ""
            return True
            
        try:
            self.driver.switch_to.default_content()
            parts = frame_path.split('/')
            
            for part in parts:
                found = False
                # 1. ID로 찾기
                try:
                    self.driver.switch_to.frame(part)
                    found = True
                    continue
                except (NoSuchFrameException, Exception):
                    pass  # ID로 찾기 실패, 다음 방법 시도
                
                # 2. WebElement로 찾기 (index=N 형식 처리)
                if part.startswith("index="):
                    idx = int(part.split("=")[1])
                    frames = self.driver.find_elements(By.TAG_NAME, "iframe")
                    if 0 <= idx < len(frames):
                        self.driver.switch_to.frame(frames[idx])
                        found = True
                        continue
                
                # 3. 그 외 (XPath 등으로 시도해볼 수 있음)
                if not found:
                    logger.warning(f"프레임을 찾을 수 없음: {part}")
                    return False
            
            self.current_frame_path = frame_path
            return True
            
        except Exception as e:
            logger.error(f"프레임 전환 실패 ({frame_path}): {e}")
            return False

    def find_element_in_all_frames(self, xpath: str, max_depth: int = 5) -> Tuple[Optional[Any], str]:
        """모든 프레임에서 요소 검색, (element, frame_path) 반환"""
        self.ensure_valid_window()
        original_handle = self.driver.current_window_handle
        
        found_element = None
        found_path = ""
        
        try:
            # 1. 메인 컨텐츠에서 먼저 검색
            self.driver.switch_to.default_content()
            try:
                el = self.driver.find_element(By.XPATH, xpath)
                return el, "main"
            except NoSuchElementException:
                pass  # 메인 컨텐츠에 요소 없음
            
            # 2. 프레임 재귀 검색
            found_element, found_path = self._search_frames(xpath, "", 0, max_depth)
            
        except Exception as e:
            logger.error(f"전체 검색 오류: {e}")
        finally:
            if not found_element:
                try:
                    self.driver.switch_to.window(original_handle)
                    self.driver.switch_to.default_content()
                except Exception as e:
                    logger.debug(f"윈도우/컨텐츠 복구 실패: {e}")
                    pass
        
        return found_element, found_path

    def _search_frames(self, xpath, parent_path="", depth=0, max_depth=5):
        if depth > max_depth:
            return None, ""
            
        try:
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
        except Exception:
            return None, ""  # iframe 검색 실패
            
        for i, frame in enumerate(iframes):
            try:
                frame_id = frame.get_attribute("id") or frame.get_attribute("name") or f"index={i}"
                current_path = f"{parent_path}/{frame_id}" if parent_path else frame_id
                
                self.driver.switch_to.frame(frame)
                
                # 요소 검색 시도
                try:
                    el = self.driver.find_element(By.XPATH, xpath)
                    # 발견!
                    return el, current_path
                except NoSuchElementException:
                    pass  # 이 프레임에 요소 없음
                
                # 재귀 호출
                el, path = self._search_frames(xpath, current_path, depth + 1, max_depth)
                if el:
                    return el, path
                
                # 복귀
                self.driver.switch_to.parent_frame()
                
            except StaleElementReferenceException:
                continue
            except Exception:
                try:
                    self.driver.switch_to.parent_frame()
                except Exception as e:
                    logger.debug(f"부모 프레임 복귀 실패 (재귀): {e}")
                    pass
                    
        return None, ""

    def get_windows(self) -> List[Dict]:
        """열린 윈도우 목록 - 안정적인 방식으로 조회"""
        if not self.is_alive():
            return []
            
        windows = []
        current_handle = ""
        try:
            current_handle = self.driver.current_window_handle
        except Exception as e:
            logger.debug(f"현재 윈도우 핸들 확인 실패 (무시): {e}")
            pass
            
        for handle in self.driver.window_handles:
            try:
                self.driver.switch_to.window(handle)
                windows.append({
                    "handle": handle,
                    "title": self.driver.title,
                    "url": self.driver.current_url,
                    "current": (handle == current_handle)
                })
            except NoSuchWindowException:
                continue
            except Exception as e:
                logger.error(f"윈도우 정보 조회 실패: {e}")
                
        # 원래 윈도우로 복귀
        if current_handle:
            try:
                self.driver.switch_to.window(current_handle)
            except Exception as e:
                # 원래 윈도우가 닫혔으면 마지막으로
                logger.debug(f"원래 윈도우 복귀 실패: {e}")
                if self.driver.window_handles:
                    self.driver.switch_to.window(self.driver.window_handles[-1])
                    
        return windows

    def switch_window(self, handle: str) -> bool:
        """윈도우 전환 - 실패시 대체 윈도우로 전환"""
        try:
            self.driver.switch_to.window(handle)
            return True
        except Exception as e:
            logger.error(f"윈도우 전환 실패: {e}")
            return self._recover_to_available_window()

    # -------------------------------------------------------------------------
    # Picker Script Injection
    # -------------------------------------------------------------------------

    def start_picker(self, overlay_mode: bool = False):
        """요소 선택 모드 시작 - 모든 iframe에 주입"""
        self.ensure_valid_window()
        
        # 메인 컨텐츠 주입 (항상 실행)
        try:
            self.driver.switch_to.default_content()
            self.driver.execute_script(PICKER_SCRIPT)
            logger.info("Main frame picker injected")
        except Exception as e:
            logger.error(f"메인 프레임 스크립트 주입 실패: {e}")

        # 모든 iframe에 재귀 주입
        self._inject_to_frames()
        
        # 다시 메인으로 복귀
        self.driver.switch_to.default_content()

    def _inject_to_frames(self, depth=0, max_depth=5):
        if depth > max_depth:
            return

        try:
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
        except Exception:
            return  # iframe 검색 실패

        for frame in iframes:
            try:
                self.driver.switch_to.frame(frame)
                
                # 스크립트 주입
                try:
                    self.driver.execute_script(PICKER_SCRIPT)
                except Exception as e:
                    pass # 보안 제한 등으로 실패할 수 있음
                
                # 재귀 탐색
                self._inject_to_frames(depth + 1, max_depth)
                
                # 부모로 복귀
                self.driver.switch_to.parent_frame()
            except Exception:
                try:
                    self.driver.switch_to.parent_frame()
                except Exception:
                    pass  # 복귀 실패 무시

    def get_picker_result(self) -> Optional[Dict]:
        """선택 결과 가져오기 - 모든 프레임에서 검색"""
        if not self.is_alive():
            return "CANCELLED"
            
        try:
            # 1. 메인 프레임 확인
            self.driver.switch_to.default_content()
            result = self.driver.execute_script("return window.__pickerResult;")
            if result:
                if isinstance(result, dict):
                    result['frame'] = 'main'
                return result
            
            # 2. iframe 확인 (재귀)
            return self._check_frames()
            
        except Exception as e:
            logger.error(f"결과 확인 중 오류: {e}")
            return None

    def _check_frames(self, path="", depth=0, max_depth=5):
        if depth > max_depth:
            return None
            
        try:
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
        except Exception:
            return None  # iframe 검색 실패
            
        for i, frame in enumerate(iframes):
            try:
                frame_id = frame.get_attribute("id") or frame.get_attribute("name") or f"index={i}"
                current_path = f"{path}/{frame_id}" if path else frame_id
                
                self.driver.switch_to.frame(frame)
                
                result = self.driver.execute_script("return window.__pickerResult;")
                if result:
                    if isinstance(result, dict):
                        result['frame'] = current_path
                    self.driver.switch_to.default_content() # 결과 찾으면 메인으로 복귀 후 리턴
                    return result
                
                # 재귀
                found = self._check_frames(current_path, depth + 1, max_depth)
                if found:
                    if isinstance(found, dict) and 'frame' not in found: # 이미 경로가 있으면 유지
                         found['frame'] = current_path
                    self.driver.switch_to.default_content()
                    return found
                    
                self.driver.switch_to.parent_frame()
            except Exception:
                try:
                    self.driver.switch_to.parent_frame()
                except Exception:
                    pass  # 복귀 실패 무시
        return None

    def is_picker_active(self) -> bool:
        """선택 모드 활성화 여부 - 모든 프레임 검사"""
        if not self.is_alive():
            return False
            
        try:
            # 메인
            self.driver.switch_to.default_content()
            active = self.driver.execute_script("return window.__pickerActive;")
            if active: return True
            
            # 프레임
            return self._check_active()
        except Exception:
            return False  # 피커 상태 확인 실패

    def _check_active(self, depth=0, max_depth=5):
        if depth > max_depth: return False
        try:
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            for frame in iframes:
                self.driver.switch_to.frame(frame)
                if self.driver.execute_script("return window.__pickerActive;"):
                    self.driver.switch_to.default_content()
                    return True
                if self._check_active(depth + 1, max_depth):
                    self.driver.switch_to.default_content()
                    return True
                self.driver.switch_to.parent_frame()
        except Exception:
            pass  # 프레임에서 피커 확인 실패
        return False
        
    def highlight(self, xpath: str, duration: int = 2500, frame_path: str = None) -> bool:
        """요소 하이라이트 - 중첩 iframe 지원"""
        self.ensure_valid_window()
        
        try:
            # 해당 프레임으로 이동
            if not self.switch_to_frame_by_path(frame_path):
                # 프레임 경로가 없거나 실패한 경우, 전체 검색 시도 (백업)
                el, found_path = self.find_element_in_all_frames(xpath)
                if not el:
                    return False
            else:
                try:
                    el = self.driver.find_element(By.XPATH, xpath)
                except NoSuchElementException:
                    return False  # 요소 없음
            
            # 하이라이트 실행
            self.driver.execute_script("""
                var el = arguments[0];
                var original = el.style.outline;
                var originalBg = el.style.backgroundColor;
                
                el.style.outline = '3px solid #00ff88';
                el.style.outlineOffset = '2px';
                el.style.backgroundColor = 'rgba(0, 255, 136, 0.2)';
                
                el.scrollIntoView({behavior: 'smooth', block: 'center'});
                
                setTimeout(function() {
                    el.style.outline = original;
                    el.style.backgroundColor = originalBg;
                }, arguments[1]);
            """, el, duration)
            
            return True
            
        except Exception as e:
            logger.error(f"하이라이트 오류: {e}")
            return False
            
    def validate_xpath(self, xpath: str) -> Dict:
        """XPath 검증 - 중첩 iframe 재귀 탐색"""
        if not self.is_alive():
            return {"found": False, "msg": "브라우저 연결 안됨"}

        # 1. 2024.12 Cloudflare 등 보안 요소로 인해 visibility 체크를 완화할 필요가 있음
        #    하지만 여기서는 우선 요소를 찾는 것 자체에 집중
        
        element, frame_path = self.find_element_in_all_frames(xpath)
        
        if element:
            try:
                tag = element.tag_name
                text = element.text[:50]
                count = 1 # find_element는 하나만 찾으므로
                # count = len(self.driver.find_elements(By.XPATH, xpath)) # 정확한 count를 위해선 동일 프레임에서 재검색 필요
                
                return {
                    "found": True,
                    "count": count,
                    "tag": tag,
                    "text": text,
                    "frame_path": frame_path
                }
            except Exception:
                return {"found": True, "msg": "요소 찾음 (상세 정보 읽기 실패)"}
        
        return {"found": False, "msg": "요소를 찾을 수 없음"}

    # =========================================================================
    # v4.0 신규: 스크린샷, 요소 카운트, 상세 정보
    # =========================================================================
    
    def count_elements(self, xpath: str, frame_path: str = None) -> int:
        """
        XPath에 매칭되는 모든 요소 개수 반환 (실시간 미리보기용)
        
        Args:
            xpath: 검색할 XPath
            frame_path: 프레임 경로 (None이면 현재 프레임)
        
        Returns:
            매칭 요소 개수 (오류 시 -1)
        """
        if not self.is_alive():
            return -1
        
        try:
            if frame_path:
                self.switch_to_frame_by_path(frame_path)
            
            elements = self.driver.find_elements(By.XPATH, xpath)
            return len(elements)
        except Exception as e:
            logger.debug(f"요소 카운트 실패: {e}")
            return -1
    
    def get_element_info(self, xpath: str, frame_path: str = None) -> Optional[Dict]:
        """
        요소의 상세 정보 반환 (Diff 분석용)
        
        Args:
            xpath: 요소 XPath
            frame_path: 프레임 경로
        
        Returns:
            {
                'found': bool,
                'tag': str,
                'id': str,
                'name': str,
                'class': str,
                'text': str,
                'attributes': dict,
                'count': int,
                'parent_tag': str,
                'parent_id': str,
                'parent_class': str,
                'index': int
            }
        """
        if not self.is_alive():
            return {'found': False, 'msg': '브라우저 연결 안됨'}
        
        try:
            # 프레임 전환
            if frame_path:
                if not self.switch_to_frame_by_path(frame_path):
                    return {'found': False, 'msg': f'프레임 전환 실패: {frame_path}'}
            
            # 요소 찾기
            try:
                element = self.driver.find_element(By.XPATH, xpath)
            except NoSuchElementException:
                return {'found': False, 'msg': '요소를 찾을 수 없음'}
            
            # 요소 정보 수집
            info = {
                'found': True,
                'tag': element.tag_name.lower(),
                'id': element.get_attribute('id') or '',
                'name': element.get_attribute('name') or '',
                'class': element.get_attribute('class') or '',
                'text': (element.text[:100] if element.text else ''),
                'count': len(self.driver.find_elements(By.XPATH, xpath))
            }
            
            # 모든 속성 수집
            try:
                attrs_script = """
                var el = arguments[0];
                var attrs = {};
                for (var i = 0; i < el.attributes.length; i++) {
                    var attr = el.attributes[i];
                    attrs[attr.name] = attr.value;
                }
                return attrs;
                """
                info['attributes'] = self.driver.execute_script(attrs_script, element)
            except Exception:
                info['attributes'] = {}
            
            # 부모 정보
            try:
                parent_script = """
                var el = arguments[0].parentElement;
                if (!el) return null;
                return {
                    tag: el.tagName.toLowerCase(),
                    id: el.id || '',
                    class: el.className || ''
                };
                """
                parent_info = self.driver.execute_script(parent_script, element)
                if parent_info:
                    info['parent_tag'] = parent_info.get('tag', '')
                    info['parent_id'] = parent_info.get('id', '')
                    info['parent_class'] = parent_info.get('class', '')
            except Exception:
                info['parent_tag'] = ''
                info['parent_id'] = ''
                info['parent_class'] = ''
            
            # 형제 중 인덱스
            try:
                index_script = """
                var el = arguments[0];
                var siblings = el.parentElement.children;
                for (var i = 0; i < siblings.length; i++) {
                    if (siblings[i] === el) return i + 1;
                }
                return 0;
                """
                info['index'] = self.driver.execute_script(index_script, element)
            except Exception:
                info['index'] = 0
            
            return info
            
        except Exception as e:
            logger.error(f"요소 정보 조회 실패: {e}")
            return {'found': False, 'msg': str(e)}
    
    def screenshot_element(self, xpath: str, save_path: str, frame_path: str = None) -> bool:
        """
        요소 스크린샷 저장
        
        Args:
            xpath: 요소 XPath
            save_path: 저장할 경로 (.png)
            frame_path: 프레임 경로
        
        Returns:
            성공 여부
        """
        if not self.is_alive():
            return False
        
        try:
            # 프레임 전환
            if frame_path:
                if not self.switch_to_frame_by_path(frame_path):
                    return False
            
            # 요소 찾기
            try:
                element = self.driver.find_element(By.XPATH, xpath)
            except NoSuchElementException:
                logger.error(f"스크린샷 대상 요소 없음: {xpath}")
                return False
            
            # 스크롤하여 요소 표시
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            import time
            time.sleep(0.3)  # 스크롤 완료 대기
            
            # 스크린샷 저장
            element.screenshot(save_path)
            logger.info(f"요소 스크린샷 저장: {save_path}")
            return True
            
        except Exception as e:
            logger.error(f"스크린샷 저장 실패: {e}")
            return False
