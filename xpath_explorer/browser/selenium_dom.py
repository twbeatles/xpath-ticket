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


class BrowserDomMixin:
    def collect_dom_snapshots(
        self,
        include_frames: bool = True,
        scope: Literal["all", "current"] = "all",
    ) -> List[DomSnapshot]:
        """Collect DOM snapshots from open windows/popups and iframe documents."""
        with self._lock:
            if not self.is_alive():
                return []

            snapshots: List[DomSnapshot] = []
            original_frame_path = self.current_frame_path
            try:
                current_handle = str(self.driver.current_window_handle or "")
            except Exception:
                current_handle = ""

            windows = self.get_windows()
            if scope == "current":
                if current_handle:
                    windows = [w for w in windows if str(w.get("handle") or "") == current_handle]
                elif windows:
                    windows = windows[:1]
            if not windows and current_handle:
                metadata = self.get_current_window_metadata()
                windows = [{
                    "handle": current_handle,
                    "title": str(metadata.get("title", "") or ""),
                    "url": str(metadata.get("url", "") or ""),
                    "is_popup": bool(metadata.get("is_popup")),
                }]

            for window in windows:
                handle = str(window.get("handle") or "")
                if not handle:
                    continue

                base_title = str(window.get("title") or "")
                base_url = str(window.get("url") or "")
                is_popup = bool(window.get("is_popup"))

                try:
                    self.driver.switch_to.window(handle)
                    self.driver.switch_to.default_content()
                    self.current_frame_path = ""
                    self.frame_cache = []
                    self.frame_cache_time = 0
                except Exception as e:
                    error_text = self._short_webdriver_error(e)
                    snapshots.append(
                        DomSnapshot(
                            engine="selenium",
                            window_id=handle,
                            window_title=base_title,
                            window_url=base_url,
                            is_popup=is_popup,
                            frame_path="main",
                            frame_label="main",
                            document_url="",
                            html="",
                            error=error_text,
                            error_type=self._classify_dom_error_type(error_text),
                        )
                    )
                    continue

                try:
                    current_title = str(self.driver.title or base_title)
                except Exception:
                    current_title = base_title
                try:
                    current_url = str(self.driver.current_url or base_url)
                except Exception:
                    current_url = base_url

                frame_targets: List[Tuple[str, str]] = [("main", "main")]
                if include_frames:
                    try:
                        frames = self.get_all_frames(force_refresh=True)
                        for frame_path, frame_label in frames:
                            frame_targets.append((str(frame_path), str(frame_label)))
                    except Exception as e:
                        error_text = self._short_webdriver_error(e)
                        snapshots.append(
                            DomSnapshot(
                                engine="selenium",
                                window_id=handle,
                                window_title=current_title,
                                window_url=current_url,
                                is_popup=is_popup,
                                frame_path="frames_scan",
                                frame_label="frames_scan",
                                document_url="",
                                html="",
                                error=error_text,
                                error_type="frames_scan_failed",
                            )
                        )

                if not include_frames:
                    frame_targets = [("main", "main")]

                for frame_path, frame_label in frame_targets:
                    normalized_path = "main" if frame_path in ("", "main") else frame_path
                    normalized_label = frame_label or normalized_path
                    document_url = ""
                    html = ""
                    error_text = ""

                    try:
                        self.driver.switch_to.window(handle)
                        if normalized_path == "main":
                            self.driver.switch_to.default_content()
                            self.current_frame_path = ""
                        elif not self.switch_to_frame_by_path(normalized_path):
                            raise Exception(f"frame switch failed: {normalized_path}")

                        try:
                            document_url = str(
                                self.driver.execute_script(
                                    "return document.URL || window.location.href || '';"
                                )
                                or ""
                            )
                        except Exception:
                            document_url = current_url

                        html = str(
                            self.driver.execute_script(
                                "return document.documentElement ? document.documentElement.outerHTML : "
                                "(document.body ? document.body.outerHTML : '');"
                            )
                            or ""
                        )
                    except Exception as e:
                        error_text = self._short_webdriver_error(e)

                    snapshots.append(
                        DomSnapshot(
                            engine="selenium",
                            window_id=handle,
                            window_title=current_title,
                            window_url=current_url,
                            is_popup=is_popup,
                            frame_path=normalized_path,
                            frame_label=normalized_label,
                            document_url=document_url,
                            html=html,
                            error=error_text,
                            error_type=self._classify_dom_error_type(error_text),
                        )
                    )

            if current_handle:
                try:
                    self.driver.switch_to.window(current_handle)
                except Exception:
                    self._recover_to_available_window()

            try:
                self.switch_to_frame_by_path(original_frame_path or "main")
            except Exception:
                try:
                    self.driver.switch_to.default_content()
                    self.current_frame_path = ""
                except Exception:
                    pass

            return snapshots
