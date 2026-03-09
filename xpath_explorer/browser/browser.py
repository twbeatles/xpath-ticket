 # -*- coding: utf-8 -*-
"""
XPath Explorer Browser Manager
"""

import time 
import logging 
from contextlib import contextmanager 
from threading import RLock 
from typing import List ,Dict ,Optional ,Any ,Tuple ,Set ,cast 

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


class BrowserManager :
    """Browser manager for Selenium-based exploration."""

    def __init__ (self ):
    # 테스트 더블과 다양한 WebDriver 구현체를 모두 허용한다.
        self .driver :Any =None 
        self .current_frame_path =""#꾩옱 쒖꽦 꾨젅쎈줈
        self .frame_cache =[]#먯떆꾨젅⑸줉
        self .frame_cache_time =0 #먯떆 앹꽦 쒓컙
        self .FRAME_CACHE_DURATION =FRAME_CACHE_DURATION #먯떆 좏슚 쒓컙 (
        self ._xpath_frame_hints :Dict [str ,Tuple [str ,float ]]={}
        self ._lock =RLock ()#WebDriver 묎렐 곷젹(QThread 쎌웳 ⑹)
        self ._last_alive_error :str =""
        self ._root_window_handle :str =""

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
        """꾨젅⑦뀓ㅽ듃 댁〈/먮났 ⑦뀓ㅽ듃 ㅻ땲. - frame_path None대㈃ "꾨젅꾪솚 놁씠" 꾩옱 ⑦뀓ㅽ듃댁〈/먮났⑸땲 - frame_path "main" 먮뒗 ""대㈃ default_content대룞⑸땲 - frame_path 뺣릺대떦 꾨젅꾩쑝대룞⑸땲 대뼡 덉쇅 섎뜑쇰룄 낅즺 먮옒 꾨젅꾩쑝듦뎄쒕룄섎ŉ, 듦뎄 ㅽ뙣 default_content쒖쥌 ⑹뼱⑸땲"""
        with self ._lock :
            original_frame_path =self .current_frame_path 
            try :
                if frame_path is not None :
                    if not self .switch_to_frame_by_path (frame_path ):
                        raise Exception (f"프레임 전환 실패: {frame_path }")
                yield 
            finally :
                try :
                #먮옒 꾨젅꾩쑝듦
                    self .switch_to_frame_by_path (original_frame_path if original_frame_path else "main")
                except Exception :
                #쒖쥌 ⑹뼱: default_content
                    try :
                        if self .driver :
                            self .driver .switch_to .default_content ()
                    except Exception :
                        pass 

    def create_driver (self ,use_undetected :bool =True )->bool :
        """쒕씪대쾭 앹꽦"""
        with self ._lock :
            try :
                logger .info ("뚮씪곗 쒕씪대쾭 앹꽦 쒖옉...")
                if use_undetected and UC_AVAILABLE :
                    options =uc .ChromeOptions ()
                    options .add_argument ('--start-maximized')
                    options .add_argument ('--disable-popup-blocking')
                    options .add_argument ('--lang=ko-KR')
                    self .driver =uc .Chrome (options =options ,use_subprocess =True )
                    logger .info ("Undetected Chrome 쒕씪대쾭 앹꽦 꾨즺")
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
                    logger .info ("쒖 Chrome 쒕씪대쾭 앹꽦 꾨즺")

                try :
                    self ._root_window_handle =self .driver .current_window_handle 
                except Exception :
                    self ._root_window_handle =""

                return True 
            except Exception as e :
                logger .error (f"드라이버 생성 실패: {e }")
                return False 

    def close (self ):
        """뚮씪곗 リ린"""
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

    def _invalidate_frame_cache (self ):
        """Invalidate cached frame metadata."""
        with self ._lock :
            self .frame_cache =[]
            self .frame_cache_time =0 
            self .current_frame_path =""
            self ._xpath_frame_hints .clear ()

    def is_alive (self )->bool :
        """곌껐 곹깭 뺤씤 - 꾩옱 덈룄곌 ロㅻⅨ 덈룄곕줈 먮룞 꾪솚"""
        with self ._lock :
            if not self .driver :
                return False 
            try :
            #꾩옱 덈룄몃뱾 뺤씤 쒕룄
                _ =self .driver .current_window_handle 
                self ._last_alive_error =""
                return True 
            except NoSuchWindowException :
                logger .warning ("꾩옱 덈룄곌 ロ듬땲 ㅻⅨ 덈룄곕줈 꾪솚쒕룄⑸땲")
                return self ._recover_to_available_window ()
            except WebDriverException as e :
            #invalid session 듦뎄 곸씠 꾨땲됱떆 뺣━댁빞 쎄퀬 ㅽ뙵덉텣
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
                    logger .error ("ъ슜 ν븳 덈룄곌 놁뒿덈떎.")
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

    def ensure_valid_window (self ):
        """좏슚덈룄곹깭 댁옣 (몃먯꽌 몄텧"""
        with self ._lock :
            if not self .is_alive ():
                raise Exception ("뚮씪곗 곌껐섏 딆븯듬땲")

    def navigate (self ,url :str ):
        """URL 대룞"""
        with self ._lock :
            if self .is_alive ():
                try :
                    self .driver .get (url )
                    self ._invalidate_frame_cache ()#ㅻ퉬뚯씠먯떆 댄슚
                except Exception as e :
                    logger .error (f"이동 실패: {e }")

                    # -------------------------------------------------------------------------
                    #Frame Element
                    # -------------------------------------------------------------------------

    def get_all_frames (self ,max_depth :int =MAX_FRAME_DEPTH )->List [tuple ]:
        """⑤뱺 iframeш곸쑝먯깋 (명꽣뚰겕 묒꺽 iframe"""
        with self ._lock :
            self .ensure_valid_window ()
            #먯떆 뺤씤
            current_time =time .time ()
            if (self .frame_cache and 
            current_time -self .frame_cache_time <self .FRAME_CACHE_DURATION ):
                return self .frame_cache .copy ()

            frames_list =[]
            original_handle =self .driver .current_window_handle 

            try :
            #붿씤 ⑦뀗좊줈 덇린
                self .driver .switch_to .default_content ()
                self ._scan_frames (frames_list ,"",0 ,max_depth )

                #먯떆 낅뜲댄듃
                self .frame_cache =frames_list .copy ()
                self .frame_cache_time =current_time 

            except Exception as e :
                logger .error (f"프레임 스캔 중 오류: {e }")
                #ㅻ쪟 쒖깮 먯떆 덇린
                self .frame_cache =[]
                self .frame_cache_time =0 
            finally :
            #듦뎄
                try :
                    self .driver .switch_to .window (original_handle )
                    self .driver .switch_to .default_content ()
                    self .current_frame_path =""#꾨젅쎈줈 덇린
                except Exception as e :
                    logger .debug (f"프레임 복구 중 오류: {e }")
                    #듦뎄 ㅽ뙣 먯떆 댄슚꾨젅쎈줈 덇린
                    self .frame_cache =[]
                    self .frame_cache_time =0 
                    self .current_frame_path =""

            return frames_list 

    def _scan_frames (self ,results_list ,parent_path :str ="",depth :int =0 ,max_depth :int =MAX_FRAME_DEPTH ):
        if depth >max_depth :
            return 

            #꾩옱 ⑦뀓ㅽ듃⑤뱺 iframe 얘린
        try :
            iframes =self .driver .find_elements (By .TAG_NAME ,"iframe")
        except Exception :
            return #iframe ㅽ뙣

        for i ,frame in enumerate (iframes ):
            identifier =f"index={i }"
            try :
            #꾨젅앸퀎(ID > Name > Index)
                frame_id =frame .get_attribute ("id")
                frame_name =frame .get_attribute ("name")

                identifier =frame_id if frame_id else (frame_name if frame_name else f"index={i }")

                #쎈줈 ъ꽦
                current_path =f"{parent_path }/{identifier }"if parent_path else identifier 

                #곌낵붽
                results_list .append ((current_path ,identifier ))

                #대떦 꾨젅꾩쑝꾪솚섏뿬 ш 먯깋
                self .driver .switch_to .frame (frame )
                self ._scan_frames (results_list ,current_path ,depth +1 ,max_depth )

                #곸쐞듦
                self .driver .switch_to .parent_frame ()

            except StaleElementReferenceException :
            #꾨젅꾩씠 DOM먯꽌 щ씪
                continue 
            except Exception as e :
                logger .debug (f"프레임 하위 스캔 실패 ({identifier }): {e }")
                try :
                    self .driver .switch_to .parent_frame ()
                except Exception as e :
                    logger .debug (f"부모 프레임 복귀 실패: {e }")
                    pass 

    def switch_to_frame_by_path (self ,frame_path :str )->bool :
        """꾨젅쎈줈꾪솚 ( 'ifrmSeat/ifrmSeatDetail')"""
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
                        pass #ID얘린 ㅽ뙣, ㅼ쓬 ⑸쾿 쒕룄

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
                #ㅽ뙣 곹깭 ㅼ뿼 ⑹: default_content듦뎄, current_frame_path먮옒 좎
                try :
                    self .driver .switch_to .default_content ()
                except Exception :
                    pass 
                self .current_frame_path =original_frame_path 
                return False 

    def find_element_in_all_frames (self ,xpath :str ,max_depth :int =MAX_FRAME_DEPTH )->Tuple [Optional [Any ],str ]:
        """⑤뱺 꾨젅꾩뿉붿냼 (element, frame_path) 섑솚. 덉젙깆쓣 꾪빐 iframe먯꽌 쒓껄쎌슦 element섑솚섏 딄퀬(frame ⑦뀓ㅽ듃 욎 딄린 ъ), frame_path섑솚⑸땲 몄텧먮뒗 frame_path꾪솚 ъ“뚰븯⑹떇쇰줈 ъ슜섏꽭"""
        with perf_span ("browser.find_element_in_all_frames"):
            with self ._lock :
                self .ensure_valid_window ()

                original_handle =self .driver .current_window_handle 
                original_frame_path =self .current_frame_path 

                found_element :Optional [Any ]=None 
                found_path =""

                try :
                #1. 붿씤 ⑦뀗좎뿉쇱
                    self .driver .switch_to .default_content ()
                    try :
                        self .driver .find_element (By .XPATH ,xpath )
                        found_path ="main"
                        return None ,found_path 
                    except NoSuchElementException :
                        pass 

                        #2. 꾨젅ш (search ⑥닔긽 parent_frame뺣━
                    found_path =self ._find_xpath_in_frames (xpath ,"",0 ,max_depth )
                    if found_path :
                    #element몄텧먭 frame_pathъ“뚰븯꾨줉 좊룄 (⑦뀓ㅽ듃 ㅼ뿼 ⑹)
                        return None ,found_path 

                except Exception as e :
                    logger .error (f"전체 검색 오류: {e }")
                finally :
                #긽 먮옒 ⑦뀓ㅽ듃듦뎄
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
        """⑤뱺 꾨젅꾩뿉XPath됲븯 쒓껄 frame_path섑솚. (꾨젅ㅽ깮 긽 parent_frame뺣━섎룄ъ꽦)"""
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
                #꾩옱 꾨젅꾩뿉쇱
                    try :
                        self .driver .find_element (By .XPATH ,xpath )
                        return current_path 
                    except NoSuchElementException :
                        pass 

                        #섏쐞 꾨젅ш
                    found =self ._find_xpath_in_frames (xpath ,current_path ,depth +1 ,max_depth )
                    if found :
                        return found 
                finally :
                    try :
                        self .driver .switch_to .parent_frame ()
                    except Exception :
                    #parent_frame ㅽ뙣 default_content듦뎄(곹깭 ㅼ뿼 ⑹)
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
            #ㅼ쓬 꾨젅먯깋
                try :
                    self .driver .switch_to .parent_frame ()
                except Exception :
                    try :
                        self .driver .switch_to .default_content ()
                    except Exception :
                        pass 
                continue 

        return ""

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
                }
        except Exception :
            return None 

    def get_windows (self )->List [Dict ]:
        """대┛ 덈룄⑸줉 - 앹뾽 곗꽑 뺣젹고쉶"""
        with self ._lock :
            if not self .is_alive ():
                return []

            windows =[]
            current_handle =""
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

                    #먮옒 덈룄곕줈 듦
            if current_handle :
                try :
                    self .driver .switch_to .window (current_handle )
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
        """덈룄꾪솚 - ㅽ뙣덈룄곕줈 꾪솚"""
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
                    logger .debug ("덈룄꾪솚 ㅽ뙣: %s",self ._short_webdriver_error (e ))
                except Exception as e :
                    logger .debug ("덈룄꾪솚 ㅽ뙣: %s",e )

            logger .warning ("붿껌덈룄꾪솚섏 삵빐 듦뎄섏쟾: %s",handle )
            return self ._recover_to_available_window (preferred_handle =handle )

            # -------------------------------------------------------------------------
            # Picker Script Injection
            # -------------------------------------------------------------------------

    def start_picker (self ,overlay_mode :bool =False ):
        """붿냼 좏깮 ⑤뱶 쒖옉 - ⑤뱺 덈룄앹뾽 곗꽑) + iframe쇱엯"""
        with self ._lock :
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
            return #iframe ㅽ뙣

        for frame in iframes :
            try :
                self .driver .switch_to .frame (frame )
                abort =False 
                try :
                #ㅽ겕쏀듃 쇱엯
                    try :
                        self .driver .execute_script (PICKER_SCRIPT )
                    except Exception :
                        pass #댁븞 쒗븳 깆쑝ㅽ뙣덉쓬

                        #ш 먯깋
                    self ._inject_to_frames (depth +1 ,max_depth )
                finally :
                    try :
                        self .driver .switch_to .parent_frame ()
                    except Exception :
                    #parent_frame ㅽ뙣 ⑦뀓ㅽ듃 ㅼ뿼 ⑹
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
                                result ["is_popup"]=bool (
                                self ._root_window_handle and handle !=self ._root_window_handle 
                                )
                            return result 

                        result =self ._find_picker_result_in_frames ()
                        if result and isinstance (result ,dict ):
                            result ["window_handle"]=handle 
                            result ["window_title"]=self .driver .title 
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
        """꾨젅꾩쓣 ш곸쑝먯깋섏뿬 picker result얠쓬 (긽 parent_frame 뺣━)"""
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
                    #섏쐞먯꽌 얠 쎌슦 frame 쎈줈 놁쑝닿컯
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

    def highlight (self ,xpath :str ,duration :int =2500 ,frame_path :Optional [str ]=None )->bool :
        """Highlight matched element, including nested iframe context."""
        with self .frame_context ():
            self .ensure_valid_window ()

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
                        return False 
                    effective_frame =found_path 

                with self .frame_context (effective_frame ):
                    try :
                        el =self .driver .find_element (By .XPATH ,xpath )
                    except NoSuchElementException :
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

                return True 

            except Exception as e :
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
                    if found :
                        self ._set_xpath_frame_hint (xpath ,frame_path )
                        self ._session_set_hint (session ,xpath ,frame_path )
                        return found 

                        #4) 몄뀡 꾨젅쒗쉶
                session_frames =session .get ("frames")if isinstance (session ,dict )else None 
                if isinstance (session_frames ,list ):
                    for frame_path in session_frames :
                        if not frame_path or frame_path in tried :
                            continue 
                        tried .add (frame_path )
                        found =self ._try_find_in_frame (xpath ,frame_path )
                        if found :
                            self ._set_xpath_frame_hint (xpath ,frame_path )
                            self ._session_set_hint (session ,xpath ,frame_path )
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
                if not found :
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
                return -1 

            try :
                if frame_path is not None :
                    with self .frame_context (frame_path ):
                        return len (self .driver .find_elements (By .XPATH ,xpath ))
                return len (self .driver .find_elements (By .XPATH ,xpath ))
            except Exception as e :
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
                return False 

            try :
                if frame_path is not None :
                    if not self .switch_to_frame_by_path (frame_path ):
                        return False 

                try :
                    element =self .driver .find_element (By .XPATH ,xpath )
                except NoSuchElementException :
                    logger .error (f"스크린샷 대상 요소 없음: {xpath }")
                    return False 

                self .driver .execute_script ("arguments[0].scrollIntoView({block: 'center'});",element )
                time .sleep (0.3 )

                element .screenshot (save_path )
                logger .info (f"요소 스크린샷 저장: {save_path }")
                return True 

            except Exception as e :
                logger .error (f"스크린샷 저장 실패: {e }")
                return False 

    def collect_dom_snapshots (self ,include_frames :bool =True )->List [DomSnapshot ]:
        """Collect DOM snapshots from all windows/popups and iframe documents."""
        with self ._lock :
            if not self .is_alive ():
                return []

            snapshots :List [DomSnapshot ]=[]
            original_frame_path =self .current_frame_path 
            try :
                current_handle =self .driver .current_window_handle 
            except Exception :
                current_handle =""

            windows =self .get_windows ()
            if not windows and current_handle :
                windows =[{
                "handle":current_handle ,
                "title":"",
                "url":"",
                "is_popup":False ,
                }]

            for window in windows :
                handle =str (window .get ("handle")or "")
                if not handle :
                    continue 

                base_title =str (window .get ("title")or "")
                base_url =str (window .get ("url")or "")
                is_popup =bool (window .get ("is_popup"))

                try :
                    self .driver .switch_to .window (handle )
                    self .driver .switch_to .default_content ()
                    self .current_frame_path =""
                    # get_all_frames() 캐시가 다른 창 결과를 재사용하지 않도록 창 단위로 초기화
                    self .frame_cache =[]
                    self .frame_cache_time =0 
                except Exception as e :
                    snapshots .append (
                    DomSnapshot (
                    engine ="selenium",
                    window_id =handle ,
                    window_title =base_title ,
                    window_url =base_url ,
                    is_popup =is_popup ,
                    frame_path ="main",
                    frame_label ="main",
                    document_url ="",
                    html ="",
                    error =self ._short_webdriver_error (e ),
                    )
                    )
                    continue 

                try :
                    current_title =str (self .driver .title or base_title )
                except Exception :
                    current_title =base_title 
                try :
                    current_url =str (self .driver .current_url or base_url )
                except Exception :
                    current_url =base_url 

                frame_targets :List [Tuple [str ,str ]]=[("main","main")]
                if include_frames :
                    try :
                        frames =self .get_all_frames ()
                        for frame_path ,frame_label in frames :
                            frame_targets .append ((str (frame_path ),str (frame_label )))
                    except Exception as e :
                        snapshots .append (
                        DomSnapshot (
                        engine ="selenium",
                        window_id =handle ,
                        window_title =current_title ,
                        window_url =current_url ,
                        is_popup =is_popup ,
                        frame_path ="frames_scan",
                        frame_label ="frames_scan",
                        document_url ="",
                        html ="",
                        error =self ._short_webdriver_error (e ),
                        )
                        )

                for frame_path ,frame_label in frame_targets :
                    normalized_path ="main"if frame_path in ("","main")else frame_path 
                    normalized_label =frame_label or normalized_path 
                    document_url =""
                    html =""
                    error_text =""

                    try :
                        self .driver .switch_to .window (handle )
                        if normalized_path =="main":
                            self .driver .switch_to .default_content ()
                            self .current_frame_path =""
                        elif not self .switch_to_frame_by_path (normalized_path ):
                            raise Exception (f"frame switch failed: {normalized_path }")

                        try :
                            document_url =str (
                            self .driver .execute_script (
                            "return document.URL || window.location.href || '';"
                            )
                            or ""
                            )
                        except Exception :
                            document_url =current_url 

                        html =str (
                        self .driver .execute_script (
                        "return document.documentElement ? document.documentElement.outerHTML : "
                        "(document.body ? document.body.outerHTML : '');"
                        )
                        or ""
                        )
                    except Exception as e :
                        error_text =self ._short_webdriver_error (e )

                    snapshots .append (
                    DomSnapshot (
                    engine ="selenium",
                    window_id =handle ,
                    window_title =current_title ,
                    window_url =current_url ,
                    is_popup =is_popup ,
                    frame_path =normalized_path ,
                    frame_label =normalized_label ,
                    document_url =document_url ,
                    html =html ,
                    error =error_text ,
                    )
                    )

            if current_handle :
                try :
                    self .driver .switch_to .window (current_handle )
                except Exception :
                    self ._recover_to_available_window ()

            try :
                self .switch_to_frame_by_path (original_frame_path or "main")
            except Exception :
                try :
                    self .driver .switch_to .default_content ()
                    self .current_frame_path =""
                except Exception :
                    pass 

            return snapshots 
