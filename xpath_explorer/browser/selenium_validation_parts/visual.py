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


class SeleniumValidationVisualMixin:
    def highlight (self ,xpath :str ,duration :int =2500 ,frame_path :Optional [str ]=None )->bool :
        """Highlight matched element, including nested iframe context."""
        with self .frame_context ():
            self .ensure_valid_window ()
            self ._clear_last_error ()

            try :
                effective_frame =None
                if frame_path :
                    if self .switch_to_frame_by_path (frame_path ):
                        effective_frame =frame_path
                    else :
                        effective_frame =None

                if not effective_frame :
                    _ ,found_path =self .find_element_in_all_frames (xpath )
                    if not found_path :
                        self ._set_last_error (f"요소를 찾을 수 없습니다: {xpath }")
                        return False
                    effective_frame =found_path

                with self .frame_context (effective_frame ):
                    try :
                        el =self .driver .find_element (By .XPATH ,xpath )
                    except NoSuchElementException :
                        self ._set_last_error (f"요소를 찾을 수 없습니다: {xpath }")
                        return False

                        # 하이라이트 실행
                    self .driver .execute_script ("""
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
                    """,el ,duration )

                self ._clear_last_error ()
                return True

            except Exception as e :
                self ._set_last_error (f"하이라이트 오류: {e }")
                logger .error (f"하이라이트 오류: {e }")
                return False

    def screenshot_element (self ,xpath :str ,save_path :str ,frame_path :Optional [str ]=None )->bool :
        """요소 스크린샷을 저장합니다."""
        with self .frame_context ():
            if not self .is_alive ():
                self ._set_last_error ("브라우저가 연결되지 않았습니다.")
                return False

            self ._clear_last_error ()

            try :
                if frame_path is not None :
                    if not self .switch_to_frame_by_path (frame_path ):
                        self ._set_last_error (f"프레임 전환 실패: {frame_path }")
                        return False

                try :
                    element =self .driver .find_element (By .XPATH ,xpath )
                except NoSuchElementException :
                    self ._set_last_error (f"스크린샷 대상 요소 없음: {xpath }")
                    logger .error (f"스크린샷 대상 요소 없음: {xpath }")
                    return False

                self .driver .execute_script ("arguments[0].scrollIntoView({block: 'center'});",element )
                time .sleep (0.3 )

                element .screenshot (save_path )
                self ._clear_last_error ()
                logger .info (f"요소 스크린샷 저장: {save_path }")
                return True

            except Exception as e :
                self ._set_last_error (f"스크린샷 저장 실패: {e }")
                logger .error (f"스크린샷 저장 실패: {e }")
                return False
