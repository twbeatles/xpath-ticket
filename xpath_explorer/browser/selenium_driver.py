# pyright: reportAttributeAccessIssue=false, reportCallIssue=false, reportArgumentType=false, reportRedeclaration=false
 # -*- coding: utf-8 -*-
"""
XPath Explorer Browser Manager
"""

import time 
import logging 
from contextlib import contextmanager 
from threading import RLock 
from typing import List ,Dict ,Optional ,Any ,Tuple ,Set ,cast ,Literal 

from xpath_explorer .core .constants import (
PICKER_SCRIPT ,
MAX_FRAME_DEPTH ,
FRAME_CACHE_DURATION ,
VALIDATION_MISS_TTL_SECONDS ,
)
from xpath_explorer .browser .dom_export import DomSnapshot 
from xpath_explorer .core .perf import perf_span 

# 로거 설정
logger =logging .getLogger ('XPathExplorer')

# Selenium Imports
webdriver :Any =None 
Service :Any =None 
Options :Any =None 
By :Any =None 
Keys :Any =None 
ActionChains :Any =None 
WebDriverWait :Any =None 
EC :Any =None 
NoSuchWindowException =Exception 
WebDriverException =Exception 
NoSuchFrameException =Exception 
StaleElementReferenceException =Exception 
NoSuchElementException =Exception 
InvalidSelectorException =Exception 
try :
    from selenium import webdriver 
    from selenium .webdriver .chrome .service import Service 
    from selenium .webdriver .chrome .options import Options 
    from selenium .webdriver .common .by import By 
    from selenium .webdriver .common .keys import Keys 
    from selenium .webdriver .common .action_chains import ActionChains 
    from selenium .webdriver .support .ui import WebDriverWait 
    from selenium .webdriver .support import expected_conditions as EC 
    from selenium .common .exceptions import (
    InvalidSelectorException ,
    NoSuchElementException ,
    NoSuchFrameException ,
    NoSuchWindowException ,
    StaleElementReferenceException ,
    WebDriverException ,
    )
    SELENIUM_AVAILABLE =True 
except ImportError :
    SELENIUM_AVAILABLE =False 
    logger .error ("Selenium 모듈이 설치되지 않았습니다.")
    class _ByFallback :
        TAG_NAME ="tag name"
        XPATH ="xpath"
    By =_ByFallback ()

uc :Any =None 
try :
    import undetected_chromedriver as uc 
    UC_AVAILABLE =True 
except ImportError :
    UC_AVAILABLE =False 

ChromeDriverManager :Any =None 
try :
    from webdriver_manager .chrome import ChromeDriverManager 
    WDM_AVAILABLE =True 
except ImportError :
    WDM_AVAILABLE =False 


class BrowserDriverMixin:
    def __init__ (self ):
    # 테스트 더블과 다양한 WebDriver 구현체를 모두 허용한다.
        self .driver :Any =None 
        self .current_frame_path =""# 현재 활성 프레임 경로
        self .frame_cache =[]# 프레임 캐시 목록
        self .frame_cache_time =0 # 캐시 생성 시간
        self .FRAME_CACHE_DURATION =FRAME_CACHE_DURATION # 캐시 유효 시간
        self ._xpath_frame_hints :Dict [str ,Tuple [str ,float ]]={}
        self ._lock =RLock ()#WebDriver 묎렐 곷젹(QThread 쎌웳 ⑹)
        self ._last_alive_error :str =""
        self .last_error :str =""
        self ._root_window_handle :str =""

    def _set_last_error (self ,message :str ):
        self .last_error =str (message or "")

    def _clear_last_error (self ):
        self .last_error =""

    @staticmethod
    def _classify_dom_error_type(error_text: str) -> str:
        lowered = str(error_text or "").lower()
        if not lowered:
            return ""
        if "no such window" in lowered or "target window already closed" in lowered or "closed:" in lowered:
            return "closed_window"
        if "detached" in lowered:
            return "detached_frame"
        if "access denied" in lowered:
            return "access_denied"
        if "cross-origin" in lowered or "cross origin" in lowered:
            return "cross_origin"
        if "frame switch failed" in lowered or "frame scan" in lowered:
            return "frames_scan_failed"
        return "unknown"

    @staticmethod 
    def _is_invalid_session_error (error :Exception )->bool :
        msg =str (error ).lower ()
        return (
        "invalid session id"in msg 
        or "session deleted"in msg 
        or "session not created"in msg 
        )

    @staticmethod 
    def _short_webdriver_error (error :Exception )->str :
        msg =getattr (error ,"msg",str (error ))
        if not msg :
            return str (error )
        return str (msg ).splitlines ()[0 ].strip ()

    def _mark_driver_dead (self ):
        """
        Drop broken driver reference immediately.
        This prevents periodic health checks from repeatedly logging the same
        invalid-session stack traces.
        """
        driver =self .driver 
        self .driver =None 
        self ._invalidate_frame_cache ()
        self ._root_window_handle =""

        # Prevent undetected_chromedriver.__del__ from retrying quit on
        # already-invalid Win handles during interpreter shutdown.
        if driver is not None and UC_AVAILABLE :
            try :
                module_name =getattr (driver .__class__ ,"__module__","")
                if module_name .startswith ("undetected_chromedriver"):
                    setattr (driver ,"quit",lambda *args ,**kwargs :None )
            except Exception :
                pass

    @contextmanager 
    def frame_context (self ,frame_path :Optional [str ]=None ):
        """프레임 컨텍스트를 임시 전환하고 종료 시 원래 프레임으로 복구합니다."""
        with self ._lock :
            original_frame_path =self .current_frame_path 
            try :
                if frame_path is not None :
                    if not self .switch_to_frame_by_path (frame_path ):
                        raise Exception (f"프레임 전환 실패: {frame_path }")
                yield 
            finally :
                try :
                # 원래 프레임으로 복구
                    self .switch_to_frame_by_path (original_frame_path if original_frame_path else "main")
                except Exception :
                # 최종 방어: default_content로 복구
                    try :
                        if self .driver :
                            self .driver .switch_to .default_content ()
                    except Exception :
                        pass

    def create_driver (self ,use_undetected :bool =True )->bool :
        """드라이버 생성."""
        with self ._lock :
            try :
                self ._clear_last_error ()
                logger .info ("브라우저 드라이버 생성 시작...")
                if use_undetected and UC_AVAILABLE :
                    options =uc .ChromeOptions ()
                    options .add_argument ('--start-maximized')
                    options .add_argument ('--disable-popup-blocking')
                    options .add_argument ('--lang=ko-KR')
                    self .driver =uc .Chrome (options =options ,use_subprocess =True )
                    logger .info ("Undetected Chrome 드라이버 생성 완료")
                else :
                    options =Options ()
                    options .add_argument ('--start-maximized')
                    options .add_argument ('--disable-popup-blocking')
                    options .add_argument ('--lang=ko-KR')
                    options .add_argument ('--disable-blink-features=AutomationControlled')
                    options .add_experimental_option ('excludeSwitches',['enable-automation'])

                    if WDM_AVAILABLE :
                        service =Service (ChromeDriverManager ().install ())
                        self .driver =webdriver .Chrome (service =service ,options =options )
                    else :
                        self .driver =webdriver .Chrome (options =options )
                    logger .info ("표준 Chrome 드라이버 생성 완료")

                try :
                    self ._root_window_handle =self .driver .current_window_handle 
                except Exception :
                    self ._root_window_handle =""

                self ._clear_last_error ()
                return True 
            except Exception as e :
                self ._set_last_error (f"드라이버 생성 실패: {e }")
                logger .error (f"드라이버 생성 실패: {e }")
                return False

    def close (self ):
        """브라우저 종료."""
        with self ._lock :
            if not self .driver :
                return 
            driver =self .driver 
            try :
                driver .quit ()
            except Exception as e :
                logger .debug (f"드라이버 종료 중 오류 (무시): {e }")
            finally :
            # __del__ double-quit noise guard (undetected_chromedriver)
                if UC_AVAILABLE :
                    try :
                        module_name =getattr (driver .__class__ ,"__module__","")
                        if module_name .startswith ("undetected_chromedriver"):
                            setattr (driver ,"quit",lambda *args ,**kwargs :None )
                    except Exception :
                        pass 
                self .driver =None 
                self ._invalidate_frame_cache ()
                self ._root_window_handle =""
                self ._clear_last_error ()

    def _invalidate_frame_cache (self ):
        """Invalidate cached frame metadata."""
        with self ._lock :
            self .frame_cache =[]
            self .frame_cache_time =0 
            self .current_frame_path =""
            self ._xpath_frame_hints .clear ()

    def is_alive (self )->bool :
        """연결 상태를 확인하고 닫힌 현재 창은 가능한 다른 창으로 복구합니다."""
        with self ._lock :
            if not self .driver :
                return False 
            try :
            # 현재 창 핸들 확인
                _ =self .driver .current_window_handle 
                self ._last_alive_error =""
                return True 
            except NoSuchWindowException :
                logger .warning ("현재 창이 닫혀 다른 창으로 복구를 시도합니다.")
                return self ._recover_to_available_window ()
            except WebDriverException as e :
            # invalid session은 복구 대상이 아니므로 드라이버를 정리한다.
                if self ._is_invalid_session_error (e ):
                    short =self ._short_webdriver_error (e )
                    if self ._last_alive_error !=short :
                        logger .warning (f"WebDriver 세션 종료 감지: {short }")
                    self ._last_alive_error =short 
                    self ._mark_driver_dead ()
                    return False 
                short =self ._short_webdriver_error (e )
                if self ._last_alive_error !=short :
                    logger .warning (f"WebDriver 연결 문제: {short }")
                self ._last_alive_error =short 
                return self ._recover_to_available_window ()
            except Exception as e :
                logger .error (f"브라우저 연결 확인 실패: {e }")
                return False

    def ensure_valid_window (self ):
        """현재 창 상태가 유효한지 보장합니다."""
        with self ._lock :
            if not self .is_alive ():
                raise Exception ("브라우저가 연결되지 않았습니다.")

    def navigate (self ,url :str ):
        """URL로 이동."""
        with self ._lock :
            if self .is_alive ():
                try :
                    self .driver .get (url )
                    self ._invalidate_frame_cache ()# 네비게이션 후 프레임 캐시 무효화
                except Exception as e :
                    logger .error (f"이동 실패: {e }")

                    # -------------------------------------------------------------------------
                    #Frame Element
                    # -------------------------------------------------------------------------
