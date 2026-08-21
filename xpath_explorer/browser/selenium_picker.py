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
from xpath_explorer .core .browser_assets .picker import picker_overlay_bootstrap
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


class BrowserPickerMixin:
    def start_picker (self ,overlay_mode :bool =False ):
        """요소 선택 모드를 시작하고 모든 윈도우/iframe에 picker를 주입합니다."""
        with self ._lock :
            self ._picker_overlay_mode = bool (overlay_mode )
            self .ensure_valid_window ()
            original_frame_path =self .current_frame_path 
            try :
                current_handle =self .driver .current_window_handle 
            except Exception :
                current_handle =""

            scan_handles =self ._picker_scan_handles ()
            if not scan_handles :
                return 

            injected_count =0 
            for handle in scan_handles :
                try :
                    self .driver .switch_to .window (handle )
                    self .driver .switch_to .default_content ()
                    self .driver .execute_script (picker_overlay_bootstrap(bool (getattr (self ,"_picker_overlay_mode",False ))))
                    self .driver .execute_script (PICKER_SCRIPT )
                    injected_count +=1 
                    self ._inject_to_frames ()
                except Exception as e :
                    logger .debug (f"윈도우 picker 주입 실패({handle [:8 ]}...): {e }")

            if current_handle :
                try :
                    self .driver .switch_to .window (current_handle )
                    self .switch_to_frame_by_path (original_frame_path or "main")
                except Exception :
                    self ._recover_to_available_window ()

            logger .info (f"Picker injected windows={injected_count }")

    def _picker_scan_handles (self )->List [str ]:
        return self ._ordered_popup_first_handles ()

    def _execute_picker_lock_script (self )->bool :
        try :
            return bool (self .driver .execute_script (
            """
                return (function() {
                    if (!window.__pickerActive) return false;
                    if (typeof window.__pickerLockCurrent === 'function') {
                        return !!window.__pickerLockCurrent();
                    }
                    return false;
                })();
                """
            ))
        except Exception :
            return False

    def _execute_picker_unlock_script (self )->bool :
        try :
            return bool (self .driver .execute_script (
            """
                return (function() {
                    if (!window.__pickerActive) return false;
                    if (typeof window.__pickerUnlock === 'function') {
                        return !!window.__pickerUnlock();
                    }
                    if (window.__pickerLocked) {
                        window.__pickerLocked = false;
                        window.__lockedData = null;
                        return true;
                    }
                    return false;
                })();
                """
            ))
        except Exception :
            return False

    def _lock_picker_in_frames (self ,depth :int =0 ,max_depth :int =MAX_FRAME_DEPTH )->bool :
        if depth >max_depth :
            return False 
        try :
            iframes =self .driver .find_elements (By .TAG_NAME ,"iframe")
        except Exception :
            return False 

        for frame in iframes :
            try :
                self .driver .switch_to .frame (frame )
                abort =False 
                try :
                    if self ._execute_picker_lock_script ():
                        return True 
                    if self ._lock_picker_in_frames (depth +1 ,max_depth ):
                        return True 
                finally :
                    try :
                        self .driver .switch_to .parent_frame ()
                    except Exception :
                        try :
                            self .driver .switch_to .default_content ()
                        except Exception :
                            pass 
                        abort =True 
                if abort :
                    return False 
            except Exception :
                continue 
        return False

    def _unlock_picker_in_frames (self ,depth :int =0 ,max_depth :int =MAX_FRAME_DEPTH )->bool :
        if depth >max_depth :
            return False 
        try :
            iframes =self .driver .find_elements (By .TAG_NAME ,"iframe")
        except Exception :
            return False 

        for frame in iframes :
            try :
                self .driver .switch_to .frame (frame )
                abort =False 
                try :
                    if self ._execute_picker_unlock_script ():
                        return True 
                    if self ._unlock_picker_in_frames (depth +1 ,max_depth ):
                        return True 
                finally :
                    try :
                        self .driver .switch_to .parent_frame ()
                    except Exception :
                        try :
                            self .driver .switch_to .default_content ()
                        except Exception :
                            pass 
                        abort =True 
                if abort :
                    return False 
            except Exception :
                continue 
        return False

    def lock_picker_current (self )->bool :
        """앱 버튼으로 현재 호버된 요소를 강제 고정한다."""
        with self ._lock :
            if not self .is_alive ():
                return False 
            original_frame_path =self .current_frame_path 
            try :
                current_handle =self .driver .current_window_handle 
            except Exception :
                current_handle =""

            scan_handles =self ._picker_scan_handles ()
            try :
                for handle in scan_handles :
                    try :
                        self .driver .switch_to .window (handle )
                        self .driver .switch_to .default_content ()
                        if self ._execute_picker_lock_script ():
                            return True 
                        if self ._lock_picker_in_frames ():
                            return True 
                    except NoSuchWindowException :
                        continue 
                    except Exception as e :
                        logger .debug (f"picker 강제 고정 실패({handle [:8 ]}...): {e }")
                return False 
            finally :
                if current_handle :
                    try :
                        self .driver .switch_to .window (current_handle )
                        self .switch_to_frame_by_path (original_frame_path or "main")
                    except Exception :
                        self ._recover_to_available_window ()

    def unlock_picker_current (self )->bool :
        """앱 버튼으로 현재 고정을 강제 해제한다."""
        with self ._lock :
            if not self .is_alive ():
                return False 
            original_frame_path =self .current_frame_path 
            try :
                current_handle =self .driver .current_window_handle 
            except Exception :
                current_handle =""

            unlocked_any =False 
            scan_handles =self ._picker_scan_handles ()
            try :
                for handle in scan_handles :
                    try :
                        self .driver .switch_to .window (handle )
                        self .driver .switch_to .default_content ()
                        if self ._execute_picker_unlock_script ():
                            unlocked_any =True 
                        if self ._unlock_picker_in_frames ():
                            unlocked_any =True 
                    except NoSuchWindowException :
                        continue 
                    except Exception as e :
                        logger .debug (f"picker 강제 해제 실패({handle [:8 ]}...): {e }")
                return unlocked_any 
            finally :
                if current_handle :
                    try :
                        self .driver .switch_to .window (current_handle )
                        self .switch_to_frame_by_path (original_frame_path or "main")
                    except Exception :
                        self ._recover_to_available_window ()

    def _inject_to_frames (self ,depth =0 ,max_depth =MAX_FRAME_DEPTH ):
        if depth >max_depth :
            return 

        try :
            iframes =self .driver .find_elements (By .TAG_NAME ,"iframe")
        except Exception :
            return # iframe 조회 실패

        for frame in iframes :
            try :
                self .driver .switch_to .frame (frame )
                abort =False 
                try :
                # 스크립트 주입
                    try :
                        self .driver .execute_script (picker_overlay_bootstrap(bool (getattr (self ,"_picker_overlay_mode",False ))))
                        self .driver .execute_script (PICKER_SCRIPT )
                    except Exception :
                        pass # 안전하지 않은 프레임에서는 주입 실패 가능

                        # 하위 프레임 검색
                    self ._inject_to_frames (depth +1 ,max_depth )
                finally :
                    try :
                        self .driver .switch_to .parent_frame ()
                    except Exception :
                    # parent_frame 실패 시 default_content로 복구
                        try :
                            self .driver .switch_to .default_content ()
                        except Exception :
                            pass 
                        abort =True 

                if abort :
                    return 
            except Exception :
                continue

    def get_picker_result (self )->Optional [Dict [str ,Any ]|str ]:
        """Get picker result across windows (popup-first) and frames."""
        with self ._lock :
            if not self .is_alive ():
                return "CANCELLED"
            original_frame_path =self .current_frame_path 
            try :
                current_handle =self .driver .current_window_handle 
            except Exception :
                current_handle =""

            scan_handles =self ._picker_scan_handles ()

            try :
                for handle in scan_handles :
                    try :
                        self .driver .switch_to .window (handle )
                        self .driver .switch_to .default_content ()

                        result =self .driver .execute_script ("return window.__pickerResult;")
                        if result :
                            if isinstance (result ,dict ):
                                result ["frame"]="main"
                                result ["window_handle"]=handle 
                                result ["window_title"]=self .driver .title 
                                result ["window_url"]=self .driver .current_url 
                                result ["is_popup"]=bool (
                                self ._root_window_handle and handle !=self ._root_window_handle 
                                )
                            return result 

                        result =self ._find_picker_result_in_frames ()
                        if result and isinstance (result ,dict ):
                            result ["window_handle"]=handle 
                            result ["window_title"]=self .driver .title 
                            result ["window_url"]=self .driver .current_url 
                            result ["is_popup"]=bool (
                            self ._root_window_handle and handle !=self ._root_window_handle 
                            )
                            return result 
                    except NoSuchWindowException :
                        continue 
                    except Exception as e :
                        logger .debug (f"윈도우 picker 결과 확인 실패({handle [:8 ]}...): {e }")
                return None 
            finally :
                if current_handle :
                    try :
                        self .driver .switch_to .window (current_handle )
                        self .switch_to_frame_by_path (original_frame_path or "main")
                    except Exception :
                        self ._recover_to_available_window ()

    def _find_picker_result_in_frames (self ,path :str ="",depth :int =0 ,max_depth :int =MAX_FRAME_DEPTH ):
        """프레임을 재귀적으로 검색해 picker result를 찾습니다."""
        if depth >max_depth :
            return None 

        try :
            iframes =self .driver .find_elements (By .TAG_NAME ,"iframe")
        except Exception :
            return None 

        for i ,frame in enumerate (iframes ):
            try :
                frame_id =frame .get_attribute ("id")or frame .get_attribute ("name")or f"index={i }"
                current_path =f"{path }/{frame_id }"if path else frame_id 

                self .driver .switch_to .frame (frame )
                abort =False 
                try :
                    result =self .driver .execute_script ("return window.__pickerResult;")
                    if result :
                        if isinstance (result ,dict ):
                            result ['frame']=current_path 
                        return result 

                    found =self ._find_picker_result_in_frames (current_path ,depth +1 ,max_depth )
                    if found :
                    # 하위 프레임에서 찾은 경우 현재 경로를 보존
                        if isinstance (found ,dict )and 'frame'not in found :
                            found ['frame']=current_path 
                        return found 
                finally :
                    try :
                        self .driver .switch_to .parent_frame ()
                    except Exception :
                        try :
                            self .driver .switch_to .default_content ()
                        except Exception :
                            pass 
                        abort =True 

                if abort :
                    return None 
            except Exception :
                continue 

        return None

    def is_picker_active (self )->bool :
        """Check whether picker is active across windows and frames."""
        with self ._lock :
            if not self .is_alive ():
                return False 
            original_frame_path =self .current_frame_path 
            try :
                current_handle =self .driver .current_window_handle 
            except Exception :
                current_handle =""

            scan_handles =self ._picker_scan_handles ()

            try :
                for handle in scan_handles :
                    try :
                        self .driver .switch_to .window (handle )
                        self .driver .switch_to .default_content ()
                        active =self .driver .execute_script ("return window.__pickerActive;")
                        if active :
                            return True 
                        if self ._check_active_in_frames ():
                            return True 
                    except NoSuchWindowException :
                        continue 
                    except Exception :
                        continue 
                return False 
            finally :
                if current_handle :
                    try :
                        self .driver .switch_to .window (current_handle )
                        self .switch_to_frame_by_path (original_frame_path or "main")
                    except Exception :
                        self ._recover_to_available_window ()

    def _check_active_in_frames (self ,depth :int =0 ,max_depth :int =MAX_FRAME_DEPTH )->bool :
        if depth >max_depth :
            return False 

        try :
            iframes =self .driver .find_elements (By .TAG_NAME ,"iframe")
        except Exception :
            return False 

        for frame in iframes :
            try :
                self .driver .switch_to .frame (frame )
                abort =False 
                try :
                    if self .driver .execute_script ("return window.__pickerActive;"):
                        return True 
                    if self ._check_active_in_frames (depth +1 ,max_depth ):
                        return True 
                finally :
                    try :
                        self .driver .switch_to .parent_frame ()
                    except Exception :
                        try :
                            self .driver .switch_to .default_content ()
                        except Exception :
                            pass 
                        abort =True 

                if abort :
                    return False 
            except Exception :
                continue 

        return False
