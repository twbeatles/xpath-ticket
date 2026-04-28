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


class BrowserFrameMixin:
    def get_all_frames (self ,max_depth :int =MAX_FRAME_DEPTH ,force_refresh :bool =False )->List [tuple ]:
        """모든 iframe을 재귀적으로 스캔합니다."""
        with self ._lock :
            self .ensure_valid_window ()
            # 캐시 확인
            current_time =time .time ()
            if ((not force_refresh )and self .frame_cache and 
            current_time -self .frame_cache_time <self .FRAME_CACHE_DURATION ):
                return self .frame_cache .copy ()

            frames_list =[]
            original_handle =self .driver .current_window_handle 

            try :
            # 메인 컨텍스트에서 스캔 시작
                self .driver .switch_to .default_content ()
                self ._scan_frames (frames_list ,"",0 ,max_depth )

                # 캐시 업데이트
                self .frame_cache =frames_list .copy ()
                self .frame_cache_time =current_time 

            except Exception as e :
                logger .error (f"프레임 스캔 중 오류: {e }")
                # 오류 발생 시 캐시 초기화
                self .frame_cache =[]
                self .frame_cache_time =0 
            finally :
            # 복구
                try :
                    self .driver .switch_to .window (original_handle )
                    self .driver .switch_to .default_content ()
                    self .current_frame_path =""# 프레임 경로 초기화
                except Exception as e :
                    logger .debug (f"프레임 복구 중 오류: {e }")
                    # 복구 실패 시 캐시와 프레임 경로 초기화
                    self .frame_cache =[]
                    self .frame_cache_time =0 
                    self .current_frame_path =""

            return frames_list

    def _scan_frames (self ,results_list ,parent_path :str ="",depth :int =0 ,max_depth :int =MAX_FRAME_DEPTH ):
        if depth >max_depth :
            return 

            # 현재 컨텍스트의 iframe 수집
        try :
            iframes =self .driver .find_elements (By .TAG_NAME ,"iframe")
        except Exception :
            return # iframe 조회 실패

        for i ,frame in enumerate (iframes ):
            identifier =f"index={i }"
            try :
            # 프레임 식별자 우선순위: ID > name > index
                frame_id =frame .get_attribute ("id")
                frame_name =frame .get_attribute ("name")

                identifier =frame_id if frame_id else (frame_name if frame_name else f"index={i }")

                #쎈줈 ъ꽦
                current_path =f"{parent_path }/{identifier }"if parent_path else identifier 

                #곌낵붽
                results_list .append ((current_path ,identifier ))

                # 해당 프레임으로 전환하여 하위 프레임 스캔
                self .driver .switch_to .frame (frame )
                self ._scan_frames (results_list ,current_path ,depth +1 ,max_depth )

                #곸쐞듦
                self .driver .switch_to .parent_frame ()

            except StaleElementReferenceException :
            # 프레임이 DOM에서 사라짐
                continue 
            except Exception as e :
                logger .debug (f"프레임 하위 스캔 실패 ({identifier }): {e }")
                try :
                    self .driver .switch_to .parent_frame ()
                except Exception as e :
                    logger .debug (f"부모 프레임 복귀 실패: {e }")
                    pass

    def switch_to_frame_by_path (self ,frame_path :str )->bool :
        """프레임 경로로 전환합니다. 예: 'ifrmSeat/ifrmSeatDetail'."""
        with self ._lock :
            self .ensure_valid_window ()
            original_frame_path =self .current_frame_path 

            if not frame_path or frame_path =="main":
                try :
                    self .driver .switch_to .default_content ()
                    self .current_frame_path =""
                    return True 
                except Exception as e :
                    logger .error (f"default_content 전환 실패: {e }")
                    return False 

            try :
                self .driver .switch_to .default_content ()
                parts =frame_path .split ('/')

                for part in parts :
                    found =False 
                    #1. ID/Name얘린
                    try :
                        self .driver .switch_to .frame (part )
                        found =True 
                        continue 
                    except (NoSuchFrameException ,Exception ):
                        pass # ID/Name 전환 실패, 다음 방법 시도

                        #2. WebElement얘린 (index=N 뺤떇 섎━)
                    if part .startswith ("index="):
                        idx =int (part .split ("=")[1 ])
                        frames =self .driver .find_elements (By .TAG_NAME ,"iframe")
                        if 0 <=idx <len (frames ):
                            self .driver .switch_to .frame (frames [idx ])
                            found =True 
                            continue 

                    if not found :
                        raise Exception (f"프레임을 찾을 수 없음: {part }")

                        #깃났 쒖뿉곹깭 낅뜲댄듃
                self .current_frame_path =frame_path 
                return True 

            except Exception as e :
                logger .error (f"프레임 전환 실패 ({frame_path }): {e }")
                # 실패 상태 정리: default_content로 복귀하고 current_frame_path는 원래 값 유지
                try :
                    self .driver .switch_to .default_content ()
                except Exception :
                    pass 
                self .current_frame_path =original_frame_path 
                return False

    def find_element_in_all_frames (self ,xpath :str ,max_depth :int =MAX_FRAME_DEPTH )->Tuple [Optional [Any ],str ]:
        """모든 프레임에서 XPath를 찾아 발견된 frame_path를 반환합니다."""
        with perf_span ("browser.find_element_in_all_frames"):
            with self ._lock :
                self .ensure_valid_window ()

                original_handle =self .driver .current_window_handle 
                original_frame_path =self .current_frame_path 

                found_element :Optional [Any ]=None 
                found_path =""

                try :
                # 1. 메인 컨텍스트에서 먼저 검색
                    self .driver .switch_to .default_content ()
                    try :
                        self .driver .find_element (By .XPATH ,xpath )
                        found_path ="main"
                        return None ,found_path 
                    except NoSuchElementException :
                        pass 

                        # 2. 프레임 재귀 검색
                    found_path =self ._find_xpath_in_frames (xpath ,"",0 ,max_depth )
                    if found_path :
                    # 호출자가 frame_path로 다시 전환해 element를 조회하도록 경로만 반환
                        return None ,found_path 

                except Exception as e :
                    logger .error (f"전체 검색 오류: {e }")
                finally :
                # 항상 원래 컨텍스트로 복구
                    try :
                        self .driver .switch_to .window (original_handle )
                    except Exception :
                        pass 
                    try :
                        self .switch_to_frame_by_path (original_frame_path if original_frame_path else "main")
                    except Exception :
                        try :
                            self .driver .switch_to .default_content ()
                        except Exception :
                            pass 

                return found_element ,found_path

    def _find_xpath_in_frames (self ,xpath :str ,parent_path :str ="",depth :int =0 ,max_depth :int =MAX_FRAME_DEPTH )->str :
        """모든 프레임에서 XPath를 찾고 frame_path를 반환합니다."""
        if depth >max_depth :
            return ""

        try :
            iframes =self .driver .find_elements (By .TAG_NAME ,"iframe")
        except Exception :
            return ""

        for i ,frame in enumerate (iframes ):
            try :
                frame_id =frame .get_attribute ("id")or frame .get_attribute ("name")or f"index={i }"
                current_path =f"{parent_path }/{frame_id }"if parent_path else frame_id 

                self .driver .switch_to .frame (frame )
                parent_ok =True 
                try :
                # 현재 프레임에서 검색
                    try :
                        self .driver .find_element (By .XPATH ,xpath )
                        return current_path 
                    except NoSuchElementException :
                        pass 

                        # 하위 프레임 검색
                    found =self ._find_xpath_in_frames (xpath ,current_path ,depth +1 ,max_depth )
                    if found :
                        return found 
                finally :
                    try :
                        self .driver .switch_to .parent_frame ()
                    except Exception :
                    # parent_frame 실패 시 default_content로 복구
                        try :
                            self .driver .switch_to .default_content ()
                        except Exception :
                            pass 
                        parent_ok =False 

                if not parent_ok :
                    return ""

            except StaleElementReferenceException :
                continue 
            except Exception :
            # 다음 프레임 검색
                try :
                    self .driver .switch_to .parent_frame ()
                except Exception :
                    try :
                        self .driver .switch_to .default_content ()
                    except Exception :
                        pass 
                continue 

        return ""
