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


class SeleniumValidationSessionMixin:
    def begin_validation_session (self )->Dict [str ,Any ]:
        """검증 세션을 시작하고 프레임 목록/힌트/미스 정보를 유지합니다."""
        session :Dict [str ,Any ]={
        "frames":["main"],
        "hints":{},
        "misses":{},
        "frame_signature":"main",
        }
        self ._session_refresh_frame_signature (session )
        return session

    def end_validation_session (self ,session :Optional [Dict [str ,Any ]]):
        """검증 세션 종료 훅. 현재는 no-op입니다."""
        _ =session

    @staticmethod
    def _build_frame_signature (frames :List [str ])->str :
        normalized :List [str ]=[]
        for frame_path in frames :
            if isinstance (frame_path ,str )and frame_path and frame_path not in normalized :
                normalized .append (frame_path )
        if "main"not in normalized :
            normalized .insert (0 ,"main")
        return "|".join (normalized )

    @staticmethod
    def _session_normalize_frames (session :Dict [str ,Any ])->List [str ]:
        raw_frames =session .get ("frames")
        normalized :List [str ]=[]
        if isinstance (raw_frames ,list ):
            for frame_path in raw_frames :
                if isinstance (frame_path ,str )and frame_path and frame_path not in normalized :
                    normalized .append (frame_path )
        if "main"not in normalized :
            normalized .insert (0 ,"main")
        session ["frames"]=normalized
        return normalized

    def _session_refresh_frame_signature (self ,session :Optional [Dict [str ,Any ]]):
        if not isinstance (session ,dict ):
            return

        if not isinstance (session .get ("hints"),dict ):
            session ["hints"]={}

        previous_signature =str (session .get ("frame_signature","")or "")
        frames =self ._session_normalize_frames (session )
        try :
            for frame_path ,_identifier in self .get_all_frames ():
                if frame_path not in frames :
                    frames .append (frame_path )
        except Exception :
        # Session refresh is best-effort.
            pass

        current_signature =self ._build_frame_signature (frames )
        session ["frame_signature"]=current_signature

        misses =session .get ("misses")
        if isinstance (misses ,set ):
        # Legacy session schema migration.
            misses ={}
            session ["misses"]=misses
        elif not isinstance (misses ,dict ):
            misses ={}
            session ["misses"]=misses

        if previous_signature and current_signature !=previous_signature :
            misses .clear ()

    def _session_get_hint (self ,session :Optional [Dict [str ,Any ]],xpath :str )->Optional [str ]:
        if not session :
            return None
        hints =session .get ("hints")
        if not isinstance (hints ,dict ):
            return None
        value =hints .get (xpath )
        return value if isinstance (value ,str )and value else None

    def _session_set_hint (self ,session :Optional [Dict [str ,Any ]],xpath :str ,frame_path :str ):
        if not session or not xpath or not frame_path :
            return
        hints =session .get ("hints")
        if isinstance (hints ,dict ):
            hints [xpath ]=frame_path
        misses =session .get ("misses")
        if isinstance (misses ,dict ):
            misses .pop (xpath ,None )
        frames =session .get ("frames")
        if isinstance (frames ,list ):
            if frame_path not in frames :
                frames .append (frame_path )
            session ["frame_signature"]=self ._build_frame_signature (frames )

    def _session_add_miss (self ,session :Optional [Dict [str ,Any ]],xpath :str ):
        if not session or not xpath :
            return
        misses =session .get ("misses")
        if not isinstance (misses ,dict ):
            misses ={}
            session ["misses"]=misses
        misses [xpath ]={
        "ts":time .time (),
        "frame_signature":str (session .get ("frame_signature","")or ""),
        }

    def _session_has_miss (self ,session :Optional [Dict [str ,Any ]],xpath :str )->bool :
        if not session :
            return False
        misses =session .get ("misses")
        if isinstance (misses ,set ):
            return xpath in misses
        if not isinstance (misses ,dict ):
            return False

        miss_info =misses .get (xpath )
        if not isinstance (miss_info ,dict ):
            misses .pop (xpath ,None )
            return False

        ts =miss_info .get ("ts")
        miss_signature =str (miss_info .get ("frame_signature","")or "")
        current_signature =str (session .get ("frame_signature","")or "")
        if not isinstance (ts ,(int ,float )):
            misses .pop (xpath ,None )
            return False
        if time .time ()-float (ts )>VALIDATION_MISS_TTL_SECONDS :
            misses .pop (xpath ,None )
            return False
        if miss_signature !=current_signature :
            misses .pop (xpath ,None )
            return False
        return True

    def _get_xpath_frame_hint (self ,xpath :str )->Optional [str ]:
        """최근 성공 XPath-프레임 힌트를 조회합니다. TTL을 적용합니다."""
        hint =self ._xpath_frame_hints .get (xpath )
        if not hint :
            return None
        frame_path ,ts =hint
        if time .time ()-ts >self .FRAME_CACHE_DURATION :
            self ._xpath_frame_hints .pop (xpath ,None )
            return None
        return frame_path

    def _set_xpath_frame_hint (self ,xpath :str ,frame_path :str ):
        """XPath-프레임 힌트를 저장합니다."""
        if not xpath or not frame_path :
            return
        self ._xpath_frame_hints [xpath ]=(frame_path ,time .time ())
