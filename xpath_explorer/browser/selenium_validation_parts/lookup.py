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


class SeleniumValidationLookupMixin:
    def _try_find_in_frame (self ,xpath :str ,frame_path :str )->Optional [Dict [str ,Any ]]:
        """특정 프레임에서 XPath를 찾고 기본 결과를 반환합니다."""
        try :
            with self .frame_context (frame_path ):
                element =self .driver .find_element (By .XPATH ,xpath )
                try :
                    count =len (self .driver .find_elements (By .XPATH ,xpath ))
                except Exception :
                    count =1
                return {
                "found":True ,
                "count":count ,
                "tag":element .tag_name ,
                "text":element .text [:50 ]if element .text else "",
                "frame_path":frame_path ,
                **self._window_result_metadata(),
                }
        except InvalidSelectorException as e :
            return {
            "found":False ,
            "msg":f"Invalid XPath selector: {self ._short_webdriver_error (e )}",
            "error_type":"invalid_selector",
            "frame_path":frame_path ,
            }
        except Exception :
            return None

    def validate_xpath (
    self ,
    xpath :str ,
    preferred_frame :Optional [str ]=None ,
    session :Optional [Dict [str ,Any ]]=None ,
    )->Dict :
        """XPath 검증. 세션/프레임 힌트를 활용해 iframe 탐색 비용을 줄입니다."""
        with perf_span ("browser.validate_xpath"):
            with self .frame_context ():
                if not self .is_alive ():
                    return {"found":False ,"msg":"브라우저 연결 안됨","error_type":"browser_not_connected"}

                try :
                    self .driver .find_elements (By .XPATH ,xpath )
                except InvalidSelectorException as e :
                    return {
                    "found":False ,
                    "msg":f"Invalid XPath selector: {self ._short_webdriver_error (e )}",
                    "error_type":"invalid_selector",
                    }
                except Exception :
                    pass

                self ._session_refresh_frame_signature (session )

                tried :Set [str ]=set ()
                candidate_frames :List [str ]=[]

                # 1) Try caller-provided preferred frame first.
                if preferred_frame :
                    candidate_frames .append (preferred_frame )

                    # 2) 세션 힌트
                session_hint =self ._session_get_hint (session ,xpath )
                if session_hint and session_hint not in candidate_frames :
                    candidate_frames .append (session_hint )

                    # 3) 전역 힌트
                global_hint =self ._get_xpath_frame_hint (xpath )
                if global_hint and global_hint not in candidate_frames :
                    candidate_frames .append (global_hint )

                for frame_path in candidate_frames :
                    tried .add (frame_path )
                    found =self ._try_find_in_frame (xpath ,frame_path )
                    if found and bool (found .get ("found")):
                        self ._set_xpath_frame_hint (xpath ,frame_path )
                        self ._session_set_hint (session ,xpath ,frame_path )
                        return found
                    if found and found .get ("error_type")=="invalid_selector":
                        return found

                        # 4) 세션 프레임 순회
                session_frames =session .get ("frames")if isinstance (session ,dict )else None
                if isinstance (session_frames ,list ):
                    for frame_path in session_frames :
                        if not frame_path or frame_path in tried :
                            continue
                        tried .add (frame_path )
                        found =self ._try_find_in_frame (xpath ,frame_path )
                        if found and bool (found .get ("found")):
                            self ._set_xpath_frame_hint (xpath ,frame_path )
                            self ._session_set_hint (session ,xpath ,frame_path )
                            return found
                        if found and found .get ("error_type")=="invalid_selector":
                            return found

                            # 5) 같은 프레임 시그니처에서 이미 미스 처리된 XPath는 재검색 생략
                if self ._session_has_miss (session ,xpath ):
                    return {"found":False ,"msg":"요소를 찾을 수 없음","error_type":"not_found"}

                    # 6) 최후 단계: 전체 프레임 재귀 검색
                _ ,frame_path =self .find_element_in_all_frames (xpath ,max_depth =MAX_FRAME_DEPTH )
                if not frame_path :
                    self ._session_add_miss (session ,xpath )
                    return {"found":False ,"msg":"요소를 찾을 수 없음","error_type":"not_found"}

                found =self ._try_find_in_frame (xpath ,frame_path )
                if found and found .get ("error_type")=="invalid_selector":
                    return found
                if not found or not bool (found .get ("found")):
                    self ._session_add_miss (session ,xpath )
                    return {"found":False ,"msg":"요소를 찾을 수 없음","error_type":"not_found"}

                self ._set_xpath_frame_hint (xpath ,frame_path )
                self ._session_set_hint (session ,xpath ,frame_path )
                return found

    def count_elements (self ,xpath :str ,frame_path :Optional [str ]=None )->int :
        """XPath와 매칭되는 요소 수를 반환합니다. 오류 시 -1을 반환합니다."""
        with self .frame_context ():
            if not self .is_alive ():
                self ._set_last_error ("브라우저가 연결되지 않았습니다.")
                return -1

            self ._clear_last_error ()

            try :
                if frame_path is not None :
                    with self .frame_context (frame_path ):
                        count =len (self .driver .find_elements (By .XPATH ,xpath ))
                        self ._clear_last_error ()
                        return count
                count =len (self .driver .find_elements (By .XPATH ,xpath ))
                self ._clear_last_error ()
                return count
            except Exception as e :
                self ._set_last_error (f"요소 카운트 실패: {e }")
                logger .debug (f"요소 카운트 실패: {e }")
                return -1
