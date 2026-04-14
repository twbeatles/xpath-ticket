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


class BrowserValidationMixin:
    def begin_validation_session (self )->Dict [str ,Any ]:
        """몄뀡 쒖옉. 몄뀡 댁뿉꾨젅⑸줉/덊듃 뚰듃/몄뒪 뺣낫ъ궗⑺빐 곗튂 덊븘뷀븳 꾨젅꾩닔 먯깋꾩엯덈떎."""
        session :Dict [str ,Any ]={
        "frames":["main"],
        "hints":{},
        "misses":{},
        "frame_signature":"main",
        }
        self ._session_refresh_frame_signature (session )
        return session

    def end_validation_session (self ,session :Optional [Dict [str ,Any ]]):
        """몄뀡 낅즺 섏쐞 명솚꾪빐 no-op 좎)."""
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

    def _try_find_in_frame (self ,xpath :str ,frame_path :str )->Optional [Dict [str ,Any ]]:
        """뱀젙 꾨젅꾩뿉XPath고쉶섍퀬 깃났 곕낯 곌낵섑솚."""
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

                        #섏씠쇱씠ㅽ뻾
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

    def validate_xpath (
    self ,
    xpath :str ,
    preferred_frame :Optional [str ]=None ,
    session :Optional [Dict [str ,Any ]]=None ,
    )->Dict :
        """XPath - 몄뀡/꾨젅뚰듃쒖슜묒꺽 iframe 먯깋."""
        with perf_span ("browser.validate_xpath"):
            with self .frame_context ():
                if not self .is_alive ():
                    return {"found":False ,"msg":"뚮씪곗 곌껐 덈맖"}

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

                    #2) 몄뀡 뚰듃
                session_hint =self ._session_get_hint (session ,xpath )
                if session_hint and session_hint not in candidate_frames :
                    candidate_frames .append (session_hint )

                    #3) 꾩뿭 뚰듃
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

                        #4) 몄뀡 꾨젅쒗쉶
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

                            #5) 몄뀡먯꽌 대 miss 섎━XPath꾩닔 먯깋앸왂
                if self ._session_has_miss (session ,xpath ):
                    return {"found":False ,"msg":"붿냼얠쓣 놁쓬"}

                    #6) 쒗썑 섎떒: 꾩껜 꾨젅꾩닔 먯깋
                _ ,frame_path =self .find_element_in_all_frames (xpath ,max_depth =MAX_FRAME_DEPTH )
                if not frame_path :
                    self ._session_add_miss (session ,xpath )
                    return {"found":False ,"msg":"붿냼얠쓣 놁쓬"}

                found =self ._try_find_in_frame (xpath ,frame_path )
                if found and found .get ("error_type")=="invalid_selector":
                    return found 
                if not found or not bool (found .get ("found")):
                    self ._session_add_miss (session ,xpath )
                    return {"found":False ,"msg":"붿냼얠쓣 놁쓬"}

                self ._set_xpath_frame_hint (xpath ,frame_path )
                self ._session_set_hint (session ,xpath ,frame_path )
                return found

    def _get_xpath_frame_hint (self ,xpath :str )->Optional [str ]:
        """쒓렐 깃났XPath-꾨젅뚰듃 고쉶 (TTL 곸슜)."""
        hint =self ._xpath_frame_hints .get (xpath )
        if not hint :
            return None 
        frame_path ,ts =hint 
        if time .time ()-ts >self .FRAME_CACHE_DURATION :
            self ._xpath_frame_hints .pop (xpath ,None )
            return None 
        return frame_path

    def _set_xpath_frame_hint (self ,xpath :str ,frame_path :str ):
        """XPath-꾨젅뚰듃"""
        if not xpath or not frame_path :
            return 
        self ._xpath_frame_hints [xpath ]=(frame_path ,time .time ())

        # =========================================================================
        #v4.0 좉퇋: ㅽ겕곗꺑, 붿냼 댁슫 곸꽭 뺣낫
        # =========================================================================

    def count_elements (self ,xpath :str ,frame_path :Optional [str ]=None )->int :
        """XPathㅼ묶섎뒗 ⑤뱺 붿냼 쒖닔 섑솚 (ㅼ떆몃━닿린 Args: xpath: 됲븷 XPath frame_path: 꾨젅쎈줈 (None대㈃ 꾩옱 꾨젅 Returns: ㅼ묶 붿냼 쒖닔 (ㅻ쪟 -1)"""
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

    def get_element_info (
    self ,
    xpath :str ,
    frame_path :Optional [str ]=None ,
    include_attributes :bool =True ,
    session :Optional [Dict [str ,Any ]]=None ,
    )->Optional [Dict ]:
        """붿냼곸꽭 뺣낫 섑솚 (Diff 꾩꽍 Args: xpath: 붿냼 XPath frame_path: 꾨젅쎈줈 Returns: { 'found': bool, 'tag': str, 'id': str, 'name': str, 'class': str, 'text': str, 'attributes': dict, 'count': int, 'parent_tag': str, 'parent_id': str, 'parent_class': str, 'index': int }"""
        with self .frame_context ():
            if not self .is_alive ():
                return {'found':False ,'msg':'뚮씪곗 곌껐 덈맖'}

            try :
                resolved_frame =frame_path 
                if resolved_frame is None :
                    hint =self ._session_get_hint (session ,xpath )or self ._get_xpath_frame_hint (xpath )
                    if hint :
                        resolved_frame =hint 
                    else :
                        _ ,found_path =self .find_element_in_all_frames (xpath ,max_depth =MAX_FRAME_DEPTH )
                        if found_path :
                            resolved_frame =found_path 

                if resolved_frame is not None and not self .switch_to_frame_by_path (resolved_frame ):
                    return {'found':False ,'msg':f'프레임 전환 실패: {resolved_frame }'}

                try :
                    element =self .driver .find_element (By .XPATH ,xpath )
                except NoSuchElementException :
                    return {'found':False ,'msg':'붿냼얠쓣 놁쓬'}

                info ={
                'found':True ,
                'tag':element .tag_name .lower (),
                'id':element .get_attribute ('id')or '',
                'name':element .get_attribute ('name')or '',
                'class':element .get_attribute ('class')or '',
                'text':(element .text [:100 ]if element .text else ''),
                'count':len (self .driver .find_elements (By .XPATH ,xpath )),
                'frame_path':resolved_frame or 'main',
                **self._window_result_metadata(),
                }

                if include_attributes :
                #⑤뱺 띿꽦 섏쭛
                    try :
                        attrs_script ="""
                        var el = arguments[0];
                        var attrs = {};
                        for (var i = 0; i < el.attributes.length; i++) {
                            var attr = el.attributes[i];
                            attrs[attr.name] = attr.value;
                        }
                        return attrs;
                        """
                        info ['attributes']=self .driver .execute_script (attrs_script ,element )
                    except Exception :
                        info ['attributes']={}
                else :
                    info ['attributes']={}

                    #뺣낫
                try :
                    parent_script ="""
                    var el = arguments[0].parentElement;
                    if (!el) return null;
                    return {
                        tag: el.tagName.toLowerCase(),
                        id: el.id || '',
                        class: el.className || ''
                    };
                    """
                    parent_info =self .driver .execute_script (parent_script ,element )
                    if parent_info :
                        info ['parent_tag']=parent_info .get ('tag','')
                        info ['parent_id']=parent_info .get ('id','')
                        info ['parent_class']=parent_info .get ('class','')
                except Exception :
                    info ['parent_tag']=''
                    info ['parent_id']=''
                    info ['parent_class']=''

                    #뺤젣 몃뜳
                try :
                    index_script ="""
                    var el = arguments[0];
                    var siblings = el.parentElement.children;
                    for (var i = 0; i < siblings.length; i++) {
                        if (siblings[i] === el) return i + 1;
                    }
                    return 0;
                    """
                    info ['index']=self .driver .execute_script (index_script ,element )
                except Exception :
                    info ['index']=0 

                if resolved_frame :
                    self ._set_xpath_frame_hint (xpath ,resolved_frame )
                    self ._session_set_hint (session ,xpath ,resolved_frame )
                return info 

            except Exception as e :
                logger .error (f"요소 정보 조회 실패: {e }")
                return {'found':False ,'msg':str (e )}

    def screenshot_element (self ,xpath :str ,save_path :str ,frame_path :Optional [str ]=None )->bool :
        """붿냼 ㅽ겕곗꺑 Args: xpath: 붿냼 XPath save_path: ν븷 쎈줈 (.png) frame_path: 꾨젅쎈줈 Returns: 깃났 щ"""
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
