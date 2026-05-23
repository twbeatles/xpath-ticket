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


class BrowserWindowMixin:
    def get_current_window_metadata(self) -> Dict[str, Any]:
        with self._lock:
            metadata = {
                "handle": "",
                "title": "",
                "url": "",
                "is_popup": False,
            }
            if not self.driver:
                return metadata
            try:
                handle = str(self.driver.current_window_handle or "")
            except Exception:
                handle = ""
            if not handle:
                return metadata
            try:
                title = str(self.driver.title or "")
            except Exception:
                title = ""
            try:
                url = str(self.driver.current_url or "")
            except Exception:
                url = ""
            metadata["handle"] = handle
            metadata["title"] = title
            metadata["url"] = url
            metadata["is_popup"] = bool(self._root_window_handle and handle != self._root_window_handle)
            return metadata

    def _window_result_metadata(self) -> Dict[str, Any]:
        current = self.get_current_window_metadata()
        return {
            "window_handle": str(current.get("handle", "") or ""),
            "window_title": str(current.get("title", "") or ""),
            "window_url": str(current.get("url", "") or ""),
            "is_popup": bool(current.get("is_popup")),
        }

    def resolve_window_context(self, handle: str = "", window_url: str = "", title: str = "") -> Optional[Dict[str, Any]]:
        with self._lock:
            windows = self.get_windows()
            if handle:
                for window in windows:
                    if str(window.get("handle") or "") == handle:
                        return window
            if window_url:
                for window in windows:
                    if str(window.get("url") or "") == window_url:
                        return window
            if title:
                for window in windows:
                    if str(window.get("title") or "") == title:
                        return window
            return None

    def switch_to_window_context(self, handle: str = "", window_url: str = "", title: str = "") -> bool:
        with self._lock:
            if not any((handle, window_url, title)):
                return self.is_alive()
            target = self.resolve_window_context(handle=handle, window_url=window_url, title=title)
            if not target:
                self._set_last_error("대상 창을 찾을 수 없습니다.")
                return False
            target_handle = str(target.get("handle") or "")
            if not target_handle:
                self._set_last_error("대상 창을 찾을 수 없습니다.")
                return False
            if not self.switch_window(target_handle):
                if not self.last_error:
                    self._set_last_error("대상 창으로 전환할 수 없습니다.")
                return False
            self._clear_last_error()
            return True

    def switch_to_window_by_title(self, title: str) -> bool:
        return self.switch_to_window_context(title=title)

    def switch_to_root_window(self) -> bool:
        with self._lock:
            root = str(self._root_window_handle or "")
            if not root:
                windows = self.get_windows()
                if windows:
                    root = str(windows[-1].get("handle") or "")
            if not root:
                self._set_last_error("루트 창을 찾을 수 없습니다.")
                return False
            return self.switch_window(root)

    def switch_to_latest_popup(self) -> bool:
        with self._lock:
            for window in self.get_windows():
                if bool(window.get("is_popup")):
                    return self.switch_window(str(window.get("handle") or ""))
            self._set_last_error("팝업 창을 찾을 수 없습니다.")
            return False

    def wait_for_popup(self, timeout_seconds: float = 5.0, title: str = "") -> Optional[Dict[str, Any]]:
        deadline = time.time() + max(0.0, float(timeout_seconds))
        while time.time() <= deadline:
            for window in self.get_windows():
                if not bool(window.get("is_popup")):
                    continue
                if title and str(window.get("title") or "") != title:
                    continue
                self._clear_last_error()
                return window
            time.sleep(0.05)
        self._set_last_error("팝업 창을 찾을 수 없습니다.")
        return None

    def _safe_window_handles (self )->List [str ]:
        """Return currently available window handles without raising."""
        if not self .driver :
            return []
        try :
            handles =list (self .driver .window_handles )
        except WebDriverException as e :
            if self ._is_invalid_session_error (e ):
                self ._mark_driver_dead ()
                return []
            logger .debug ("window_handles query failed: %s",self ._short_webdriver_error (e ))
            return []
        except Exception as e :
            logger .debug ("window_handles query failed: %s",e )
            return []
        return [h for h in handles if h ]

    def _ordered_popup_first_handles (self ,handles :Optional [List [str ]]=None )->List [str ]:
        """Return handles ordered as popup-first, root window last."""
        if handles is None :
            handles =self ._safe_window_handles ()
        if not handles :
            return []

        if not self ._root_window_handle or self ._root_window_handle not in handles :
            self ._root_window_handle =handles [0 ]

        root =self ._root_window_handle 
        ordered =[h for h in handles if h !=root ]
        if root in handles :
            ordered .append (root )
        return ordered

    def _recover_to_available_window (self ,preferred_handle :str ="",max_attempts :int =3 )->bool :
        """Recover to an available window handle with bounded retries."""
        with self ._lock :
            if not self .driver :
                return False 

            attempts =max (1 ,int (max_attempts ))
            for attempt in range (1 ,attempts +1 ):
                handles =self ._safe_window_handles ()
                if not handles :
                    logger .error ("사용 가능한 윈도우가 없습니다.")
                    return False 

                candidates :List [str ]=[]
                if preferred_handle and preferred_handle in handles :
                    candidates .append (preferred_handle )
                for handle in self ._ordered_popup_first_handles (handles ):
                    if handle not in candidates :
                        candidates .append (handle )

                for handle in candidates :
                    try :
                        self .driver .switch_to .window (handle )
                        self ._invalidate_frame_cache ()
                        try :
                            title =self .driver .title 
                        except Exception :
                            title =""
                        logger .info (
                        "Window recovery succeeded (attempt=%s, handle=%s, title=%s)",
                        attempt ,
                        handle ,
                        title ,
                        )
                        return True 
                    except NoSuchWindowException :
                        continue 
                    except WebDriverException as e :
                        if self ._is_invalid_session_error (e ):
                            self ._mark_driver_dead ()
                            return False 
                        logger .debug ("Window recovery switch failed: %s",self ._short_webdriver_error (e ))
                    except Exception as e :
                        logger .debug ("Window recovery switch failed: %s",e )

            logger .error ("Window recovery failed after %s attempts.",attempts )
            return False

    def get_windows (self )->List [Dict ]:
        """전체 윈도우 목록을 팝업 우선 순서로 반환합니다."""
        with self ._lock :
            if not self .is_alive ():
                return []

            windows =[]
            current_handle =""
            original_frame_path =self .current_frame_path
            try :
                current_handle =self .driver .current_window_handle 
            except Exception as e :
                logger .debug (f"현재 윈도우 핸들 확인 실패 (무시): {e }")
                pass 

            handles =self ._safe_window_handles ()
            if not handles :
                return []

            scan_handles =self ._ordered_popup_first_handles (handles )

            for order ,handle in enumerate (scan_handles ):
                try :
                    self .driver .switch_to .window (handle )
                    opener_exists =False 
                    try :
                        opener_exists =bool (self .driver .execute_script ("return !!window.opener;"))
                    except Exception :
                        opener_exists =False 

                    is_popup =(handle !=self ._root_window_handle )or opener_exists 
                    windows .append ({
                    "handle":handle ,
                    "title":self .driver .title ,
                    "url":self .driver .current_url ,
                    "current":(handle ==current_handle ),
                    "is_popup":is_popup ,
                    "_order":order ,
                    })
                except NoSuchWindowException :
                    continue 
                except Exception as e :
                    logger .error (f"윈도우 정보 조회 실패: {e }")

                    # 원래 윈도우로 복귀
            if current_handle :
                try :
                    self .driver .switch_to .window (current_handle )
                    if original_frame_path :
                        if not self .switch_to_frame_by_path (original_frame_path ):
                            self .driver .switch_to .default_content ()
                            self .current_frame_path =""
                except Exception as e :
                    logger .debug (f"원래 윈도우 복귀 실패: {e }")
                    self ._recover_to_available_window (preferred_handle =current_handle )

            windows .sort (
            key =lambda w :(
            0 if w .get ("is_popup")else 1 ,# popup first
            0 if w .get ("current")else 1 ,# current first within group
            -int (w .get ("_order",0 )),# newest first
            )
            )

            for window in windows :
                window .pop ("_order",None )

            return windows

    def switch_window (self ,handle :str )->bool :
        """윈도우 전환. 실패하면 사용 가능한 윈도우로 복구합니다."""
        with self ._lock :
            if not self .driver :
                return False 
            if not handle :
                return self ._recover_to_available_window ()

            for _ in range (3 ):
                handles =self ._safe_window_handles ()
                if not handles :
                    return False 
                if handle not in handles :
                    break 
                try :
                    self .driver .switch_to .window (handle )
                    self ._invalidate_frame_cache ()
                    return True 
                except NoSuchWindowException :
                    continue 
                except WebDriverException as e :
                    if self ._is_invalid_session_error (e ):
                        self ._mark_driver_dead ()
                        return False 
                    logger .debug ("윈도우 전환 실패: %s",self ._short_webdriver_error (e ))
                except Exception as e :
                    logger .debug ("윈도우 전환 실패: %s",e )

            logger .warning ("요청한 윈도우로 전환할 수 없어 복구를 시도합니다: %s",handle )
            return self ._recover_to_available_window (preferred_handle =handle )

            # -------------------------------------------------------------------------
            # Picker Script Injection
            # -------------------------------------------------------------------------
