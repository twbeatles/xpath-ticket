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


class SeleniumElementInfoMixin:
    def get_element_info (
    self ,
    xpath :str ,
    frame_path :Optional [str ]=None ,
    include_attributes :bool =True ,
    session :Optional [Dict [str ,Any ]]=None ,
    )->Optional [Dict ]:
        """요소 상세 정보를 반환합니다. Diff 분석과 스냅샷 저장에 사용됩니다."""
        with self .frame_context ():
            if not self .is_alive ():
                return {'found':False ,'msg':'브라우저 연결 안됨','error_type':'browser_not_connected'}

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
                    return {'found':False ,'msg':'요소를 찾을 수 없음','error_type':'not_found'}

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
                # 모든 속성 수집
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

                    # 부모 정보
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

                    # 형제 기준 인덱스
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
