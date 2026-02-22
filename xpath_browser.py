# -*- coding: utf-8 -*-
"""
XPath Explorer Browser Manager
"""

import time
import logging
from contextlib import contextmanager
from threading import RLock
from typing import List, Dict, Optional, Any, Tuple, Set

from xpath_constants import PICKER_SCRIPT, MAX_FRAME_DEPTH, FRAME_CACHE_DURATION
from xpath_perf import perf_span

# 濡쒓굅 ?ㅼ젙
logger = logging.getLogger('XPathExplorer')

# Selenium Imports
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import *
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    logger.error("Selenium 紐⑤뱢???ㅼ튂?섏? ?딆븯?듬땲??")

try:
    import undetected_chromedriver as uc
    UC_AVAILABLE = True
except ImportError:
    UC_AVAILABLE = False

try:
    from webdriver_manager.chrome import ChromeDriverManager
    WDM_AVAILABLE = True
except ImportError:
    WDM_AVAILABLE = False


class BrowserManager:
    """Browser manager for Selenium-based exploration."""
    
    def __init__(self):
        self.driver = None
        self.current_frame_path = ""  # ?꾩옱 ?쒖꽦 ?꾨젅??寃쎈줈
        self.frame_cache = []  # 罹먯떆???꾨젅??紐⑸줉
        self.frame_cache_time = 0  # 罹먯떆 ?앹꽦 ?쒓컙
        self.FRAME_CACHE_DURATION = FRAME_CACHE_DURATION  # 罹먯떆 ?좏슚 ?쒓컙 (珥?
        self._xpath_frame_hints: Dict[str, Tuple[str, float]] = {}
        self._lock = RLock()  # WebDriver ?묎렐 吏곷젹??(QThread 寃쎌웳 諛⑹?)
        self._last_alive_error: str = ""
        self._root_window_handle: str = ""

    @staticmethod
    def _is_invalid_session_error(error: Exception) -> bool:
        msg = str(error).lower()
        return (
            "invalid session id" in msg
            or "session deleted" in msg
            or "session not created" in msg
        )

    @staticmethod
    def _short_webdriver_error(error: Exception) -> str:
        msg = getattr(error, "msg", str(error))
        if not msg:
            return str(error)
        return str(msg).splitlines()[0].strip()

    def _mark_driver_dead(self):
        """
        Drop broken driver reference immediately.
        This prevents periodic health checks from repeatedly logging the same
        invalid-session stack traces.
        """
        driver = self.driver
        self.driver = None
        self._invalidate_frame_cache()
        self._root_window_handle = ""

        # Prevent undetected_chromedriver.__del__ from retrying quit on
        # already-invalid Win handles during interpreter shutdown.
        if driver is not None and UC_AVAILABLE:
            try:
                module_name = getattr(driver.__class__, "__module__", "")
                if module_name.startswith("undetected_chromedriver"):
                    setattr(driver, "quit", lambda *args, **kwargs: None)
            except Exception:
                pass

    @contextmanager
    def frame_context(self, frame_path: Optional[str] = None):
        """
        ?꾨젅??而⑦뀓?ㅽ듃 蹂댁〈/?먮났 而⑦뀓?ㅽ듃 留ㅻ땲?.

        - frame_path媛 None?대㈃ "?꾨젅???꾪솚 ?놁씠" ?꾩옱 而⑦뀓?ㅽ듃瑜?蹂댁〈/?먮났留??⑸땲??
        - frame_path媛 "main" ?먮뒗 ""?대㈃ default_content濡??대룞?⑸땲??
        - frame_path媛 吏?뺣릺硫??대떦 ?꾨젅?꾩쑝濡??대룞?⑸땲??

        ?대뼡 ?덉쇅媛 ?섎뜑?쇰룄 醫낅즺 ???먮옒 ?꾨젅?꾩쑝濡?蹂듦뎄瑜??쒕룄?섎ŉ,
        蹂듦뎄 ?ㅽ뙣 ??default_content濡?理쒖쥌 諛⑹뼱?⑸땲??
        """
        with self._lock:
            original_frame_path = self.current_frame_path
            try:
                if frame_path is not None:
                    if not self.switch_to_frame_by_path(frame_path):
                        raise Exception(f"?꾨젅???꾪솚 ?ㅽ뙣: {frame_path}")
                yield
            finally:
                try:
                    # ?먮옒 ?꾨젅?꾩쑝濡?蹂듦?
                    self.switch_to_frame_by_path(original_frame_path if original_frame_path else "main")
                except Exception:
                    # 理쒖쥌 諛⑹뼱: default_content
                    try:
                        if self.driver:
                            self.driver.switch_to.default_content()
                    except Exception:
                        pass
            
    def create_driver(self, use_undetected: bool = True) -> bool:
        """?쒕씪?대쾭 ?앹꽦"""
        with self._lock:
            try:
                logger.info("釉뚮씪?곗? ?쒕씪?대쾭 ?앹꽦 ?쒖옉...")
                if use_undetected and UC_AVAILABLE:
                    options = uc.ChromeOptions()
                    options.add_argument('--start-maximized')
                    options.add_argument('--disable-popup-blocking')
                    options.add_argument('--lang=ko-KR')
                    self.driver = uc.Chrome(options=options, use_subprocess=True)
                    logger.info("Undetected Chrome ?쒕씪?대쾭 ?앹꽦 ?꾨즺")
                else:
                    options = Options()
                    options.add_argument('--start-maximized')
                    options.add_argument('--disable-popup-blocking')
                    options.add_argument('--lang=ko-KR')
                    options.add_argument('--disable-blink-features=AutomationControlled')
                    options.add_experimental_option('excludeSwitches', ['enable-automation'])
                    
                    if WDM_AVAILABLE:
                        service = Service(ChromeDriverManager().install())
                        self.driver = webdriver.Chrome(service=service, options=options)
                    else:
                        self.driver = webdriver.Chrome(options=options)
                    logger.info("?쒖? Chrome ?쒕씪?대쾭 ?앹꽦 ?꾨즺")

                try:
                    self._root_window_handle = self.driver.current_window_handle
                except Exception:
                    self._root_window_handle = ""

                return True
            except Exception as e:
                logger.error(f"?쒕씪?대쾭 ?앹꽦 ?ㅽ뙣: {e}")
                return False
            
    def close(self):
        """釉뚮씪?곗? ?リ린"""
        with self._lock:
            if not self.driver:
                return
            driver = self.driver
            try:
                driver.quit()
            except Exception as e:
                logger.debug(f"?쒕씪?대쾭 醫낅즺 以??ㅻ쪟 (臾댁떆??: {e}")
            finally:
                # __del__ double-quit noise guard (undetected_chromedriver)
                if UC_AVAILABLE:
                    try:
                        module_name = getattr(driver.__class__, "__module__", "")
                        if module_name.startswith("undetected_chromedriver"):
                            setattr(driver, "quit", lambda *args, **kwargs: None)
                    except Exception:
                        pass
                self.driver = None
                self._invalidate_frame_cache()
                self._root_window_handle = ""
    
    def _invalidate_frame_cache(self):
        """Invalidate cached frame metadata."""
        with self._lock:
            self.frame_cache = []
            self.frame_cache_time = 0
            self.current_frame_path = ""
            self._xpath_frame_hints.clear()
            
    def is_alive(self) -> bool:
        """?곌껐 ?곹깭 ?뺤씤 - ?꾩옱 ?덈룄?곌? ?ロ????ㅻⅨ ?덈룄?곕줈 ?먮룞 ?꾪솚"""
        with self._lock:
            if not self.driver:
                return False
            try:
                # ?꾩옱 ?덈룄???몃뱾 ?뺤씤 ?쒕룄
                _ = self.driver.current_window_handle
                self._last_alive_error = ""
                return True
            except NoSuchWindowException:
                logger.warning("?꾩옱 ?덈룄?곌? ?ロ??듬땲?? ?ㅻⅨ ?덈룄?곕줈 ?꾪솚???쒕룄?⑸땲??")
                return self._recover_to_available_window()
            except WebDriverException as e:
                # invalid session? 蹂듦뎄 ??곸씠 ?꾨땲??利됱떆 ?뺣━?댁빞 寃쎄퀬 ?ㅽ뙵??硫덉텣??
                if self._is_invalid_session_error(e):
                    short = self._short_webdriver_error(e)
                    if self._last_alive_error != short:
                        logger.warning(f"WebDriver ?몄뀡 醫낅즺 媛먯?: {short}")
                    self._last_alive_error = short
                    self._mark_driver_dead()
                    return False
                short = self._short_webdriver_error(e)
                if self._last_alive_error != short:
                    logger.warning(f"WebDriver ?곌껐 臾몄젣: {short}")
                self._last_alive_error = short
                return self._recover_to_available_window()
            except Exception as e:
                logger.error(f"釉뚮씪?곗? ?곌껐 ?뺤씤 ?ㅽ뙣: {e}")
                return False
            
    def _recover_to_available_window(self) -> bool:
        """?ъ슜 媛?ν븳 ?ㅻⅨ ?덈룄?곕줈 ?먮룞 蹂듦뎄"""
        with self._lock:
            try:
                handles = self.driver.window_handles
                if handles:
                    self.driver.switch_to.window(handles[-1])  # 留덉?留?蹂댄넻 理쒖떊) ?덈룄?곕줈 ?꾪솚
                    self._invalidate_frame_cache()
                    logger.info(f"?덈룄??蹂듦뎄 ?깃났: {self.driver.title}")
                    return True
                else:
                    logger.error("?ъ슜 媛?ν븳 ?덈룄?곌? ?놁뒿?덈떎.")
                    return False
            except WebDriverException as e:
                if self._is_invalid_session_error(e):
                    self._mark_driver_dead()
                    return False
                logger.debug(f"?덈룄??蹂듦뎄 以?WebDriver ?ㅻ쪟: {self._short_webdriver_error(e)}")
                return False
            except Exception as e:
                logger.debug(f"?덈룄??蹂듦뎄 以??ㅻ쪟: {e}")
                return False

    def ensure_valid_window(self):
        """?좏슚???덈룄???곹깭 蹂댁옣 (?몃??먯꽌 ?몄텧 媛??"""
        with self._lock:
            if not self.is_alive():
                raise Exception("釉뚮씪?곗?媛 ?곌껐?섏? ?딆븯?듬땲??")
            
    def navigate(self, url: str):
        """URL ?대룞"""
        with self._lock:
            if self.is_alive():
                try:
                    self.driver.get(url)
                    self._invalidate_frame_cache()  # ?ㅻ퉬寃뚯씠????罹먯떆 臾댄슚??
                except Exception as e:
                    logger.error(f"?대룞 ?ㅽ뙣: {e}")

    # -------------------------------------------------------------------------
    # Frame 諛?Element 愿由?
    # -------------------------------------------------------------------------

    def get_all_frames(self, max_depth: int = MAX_FRAME_DEPTH) -> List[tuple]:
        """紐⑤뱺 iframe???ш??곸쑝濡??먯깋 (?명꽣?뚰겕 以묒꺽 iframe 吏??"""
        with self._lock:
            self.ensure_valid_window()
            # 罹먯떆 ?뺤씤
            current_time = time.time()
            if (self.frame_cache and 
                current_time - self.frame_cache_time < self.FRAME_CACHE_DURATION):
                return self.frame_cache.copy()
                
            frames_list = []
            original_handle = self.driver.current_window_handle
            
            try:
                # 硫붿씤 而⑦뀗痢좊줈 珥덇린??
                self.driver.switch_to.default_content()
                self._scan_frames(frames_list, "", 0, max_depth)
                
                # 罹먯떆 ?낅뜲?댄듃
                self.frame_cache = frames_list.copy()
                self.frame_cache_time = current_time
                
            except Exception as e:
                logger.error(f"?꾨젅???ㅼ틪 以??ㅻ쪟: {e}")
                # ?ㅻ쪟 諛쒖깮 ??罹먯떆 珥덇린??
                self.frame_cache = []
                self.frame_cache_time = 0
            finally:
                # 蹂듦뎄
                try:
                    self.driver.switch_to.window(original_handle)
                    self.driver.switch_to.default_content()
                    self.current_frame_path = ""  # ?꾨젅??寃쎈줈 珥덇린??
                except Exception as e:
                    logger.debug(f"?꾨젅??蹂듦뎄 以??ㅻ쪟: {e}")
                    # 蹂듦뎄 ?ㅽ뙣 ??罹먯떆 臾댄슚??諛??꾨젅??寃쎈줈 珥덇린??
                    self.frame_cache = []
                    self.frame_cache_time = 0
                    self.current_frame_path = ""
                    
            return frames_list

    def _scan_frames(self, results_list, parent_path: str = "", depth: int = 0, max_depth: int = MAX_FRAME_DEPTH):
        if depth > max_depth:
            return

        # ?꾩옱 而⑦뀓?ㅽ듃??紐⑤뱺 iframe 李얘린
        try:
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
        except Exception:
            return  # iframe 寃???ㅽ뙣

        for i, frame in enumerate(iframes):
            try:
                # ?꾨젅???앸퀎??(ID > Name > Index)
                frame_id = frame.get_attribute("id")
                frame_name = frame.get_attribute("name")
                
                identifier = frame_id if frame_id else (frame_name if frame_name else f"index={i}")
                
                # 寃쎈줈 援ъ꽦
                current_path = f"{parent_path}/{identifier}" if parent_path else identifier
                
                # 寃곌낵??異붽?
                results_list.append((current_path, identifier))
                
                # ?대떦 ?꾨젅?꾩쑝濡??꾪솚?섏뿬 ?ш? ?먯깋
                self.driver.switch_to.frame(frame)
                self._scan_frames(results_list, current_path, depth + 1, max_depth)
                
                # ?곸쐞濡?蹂듦?
                self.driver.switch_to.parent_frame()
                
            except StaleElementReferenceException:
                # ?꾨젅?꾩씠 DOM?먯꽌 ?щ씪吏?
                continue
            except Exception as e:
                logger.debug(f"?꾨젅???대? ?ㅼ틪 ?ㅽ뙣 ({identifier}): {e}")
                try:
                    self.driver.switch_to.parent_frame()
                except Exception as e:
                    logger.debug(f"遺紐??꾨젅??蹂듦? ?ㅽ뙣: {e}")
                    pass

    def switch_to_frame_by_path(self, frame_path: str) -> bool:
        """?꾨젅??寃쎈줈濡??꾪솚 (?? 'ifrmSeat/ifrmSeatDetail')"""
        with self._lock:
            self.ensure_valid_window()
            original_frame_path = self.current_frame_path
            
            if not frame_path or frame_path == "main":
                try:
                    self.driver.switch_to.default_content()
                    self.current_frame_path = ""
                    return True
                except Exception as e:
                    logger.error(f"default_content ?꾪솚 ?ㅽ뙣: {e}")
                    return False
                
            try:
                self.driver.switch_to.default_content()
                parts = frame_path.split('/')
                
                for part in parts:
                    found = False
                    # 1. ID/Name濡?李얘린
                    try:
                        self.driver.switch_to.frame(part)
                        found = True
                        continue
                    except (NoSuchFrameException, Exception):
                        pass  # ID濡?李얘린 ?ㅽ뙣, ?ㅼ쓬 諛⑸쾿 ?쒕룄
                    
                    # 2. WebElement濡?李얘린 (index=N ?뺤떇 泥섎━)
                    if part.startswith("index="):
                        idx = int(part.split("=")[1])
                        frames = self.driver.find_elements(By.TAG_NAME, "iframe")
                        if 0 <= idx < len(frames):
                            self.driver.switch_to.frame(frames[idx])
                            found = True
                            continue
                    
                    if not found:
                        raise Exception(f"?꾨젅?꾩쓣 李얠쓣 ???놁쓬: {part}")
                
                # ?깃났 ?쒖뿉留??곹깭 ?낅뜲?댄듃
                self.current_frame_path = frame_path
                return True
                
            except Exception as e:
                logger.error(f"?꾨젅???꾪솚 ?ㅽ뙣 ({frame_path}): {e}")
                # ?ㅽ뙣 ???곹깭 ?ㅼ뿼 諛⑹?: default_content濡?蹂듦뎄, current_frame_path???먮옒 媛??좎?
                try:
                    self.driver.switch_to.default_content()
                except Exception:
                    pass
                self.current_frame_path = original_frame_path
                return False

    def find_element_in_all_frames(self, xpath: str, max_depth: int = MAX_FRAME_DEPTH) -> Tuple[Optional[Any], str]:
        """
        紐⑤뱺 ?꾨젅?꾩뿉???붿냼 寃?? (element, frame_path) 諛섑솚.

        ?덉젙?깆쓣 ?꾪빐 iframe?먯꽌 諛쒓껄??寃쎌슦 element??諛섑솚?섏? ?딄퀬(frame 而⑦뀓?ㅽ듃媛 留욎? ?딄린 ?ъ?),
        frame_path留?諛섑솚?⑸땲?? ?몄텧?먮뒗 frame_path濡??꾪솚 ???ъ“?뚰븯??諛⑹떇?쇰줈 ?ъ슜?섏꽭??
        """
        with perf_span("browser.find_element_in_all_frames"):
            with self._lock:
                self.ensure_valid_window()

                original_handle = self.driver.current_window_handle
                original_frame_path = self.current_frame_path

                found_element: Optional[Any] = None
                found_path = ""

                try:
                    # 1. 硫붿씤 而⑦뀗痢좎뿉??癒쇱? 寃??
                    self.driver.switch_to.default_content()
                    try:
                        self.driver.find_element(By.XPATH, xpath)
                        found_path = "main"
                        return None, found_path
                    except NoSuchElementException:
                        pass

                    # 2. ?꾨젅???ш? 寃??(search ?⑥닔????긽 parent_frame???뺣━??
                    found_path = self._find_xpath_in_frames(xpath, "", 0, max_depth)
                    if found_path:
                        # element???몄텧?먭? frame_path濡??ъ“?뚰븯?꾨줉 ?좊룄 (而⑦뀓?ㅽ듃 ?ㅼ뿼 諛⑹?)
                        return None, found_path

                except Exception as e:
                    logger.error(f"?꾩껜 寃???ㅻ쪟: {e}")
                finally:
                    # ??긽 ?먮옒 而⑦뀓?ㅽ듃濡?蹂듦뎄
                    try:
                        self.driver.switch_to.window(original_handle)
                    except Exception:
                        pass
                    try:
                        self.switch_to_frame_by_path(original_frame_path if original_frame_path else "main")
                    except Exception:
                        try:
                            self.driver.switch_to.default_content()
                        except Exception:
                            pass

                return found_element, found_path

    def _find_xpath_in_frames(self, xpath: str, parent_path: str = "", depth: int = 0, max_depth: int = MAX_FRAME_DEPTH) -> str:
        """
        紐⑤뱺 ?꾨젅?꾩뿉??XPath瑜?寃?됲븯怨? 諛쒓껄 ??frame_path瑜?諛섑솚.
        (?꾨젅???ㅽ깮? ??긽 parent_frame濡??뺣━?섎룄濡?援ъ꽦)
        """
        if depth > max_depth:
            return ""

        try:
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
        except Exception:
            return ""

        for i, frame in enumerate(iframes):
            try:
                frame_id = frame.get_attribute("id") or frame.get_attribute("name") or f"index={i}"
                current_path = f"{parent_path}/{frame_id}" if parent_path else frame_id

                self.driver.switch_to.frame(frame)
                parent_ok = True
                try:
                    # ?꾩옱 ?꾨젅?꾩뿉??癒쇱? 寃??
                    try:
                        self.driver.find_element(By.XPATH, xpath)
                        return current_path
                    except NoSuchElementException:
                        pass

                    # ?섏쐞 ?꾨젅???ш?
                    found = self._find_xpath_in_frames(xpath, current_path, depth + 1, max_depth)
                    if found:
                        return found
                finally:
                    try:
                        self.driver.switch_to.parent_frame()
                    except Exception:
                        # parent_frame ?ㅽ뙣 ??default_content濡?蹂듦뎄(?곹깭 ?ㅼ뿼 諛⑹?)
                        try:
                            self.driver.switch_to.default_content()
                        except Exception:
                            pass
                        parent_ok = False

                if not parent_ok:
                    return ""

            except StaleElementReferenceException:
                continue
            except Exception:
                # ?ㅼ쓬 ?꾨젅???먯깋 吏??
                try:
                    self.driver.switch_to.parent_frame()
                except Exception:
                    try:
                        self.driver.switch_to.default_content()
                    except Exception:
                        pass
                continue

        return ""

    def begin_validation_session(self) -> Dict[str, Any]:
        """
        寃利??몄뀡 ?쒖옉.

        ?몄뀡 ?댁뿉???꾨젅??紐⑸줉/?덊듃 ?뚰듃/誘몄뒪 ?뺣낫瑜??ъ궗?⑺빐
        諛곗튂 寃利???遺덊븘?뷀븳 ?꾨젅???꾩닔 ?먯깋??以꾩엯?덈떎.
        """
        session: Dict[str, Any] = {
            "frames": ["main"],
            "hints": {},
            "misses": set(),
        }
        try:
            for frame_path, _identifier in self.get_all_frames():
                if frame_path not in session["frames"]:
                    session["frames"].append(frame_path)
        except Exception:
            # ?몄뀡? 理쒖꽑??罹먯떆?대?濡??ㅽ뙣?대룄 寃利??먯껜??怨꾩냽 ?숈옉?댁빞 ??
            pass
        return session

    def end_validation_session(self, session: Optional[Dict[str, Any]]):
        """寃利??몄뀡 醫낅즺 ???섏쐞 ?명솚???꾪빐 no-op ?좎?)."""
        _ = session

    def _session_get_hint(self, session: Optional[Dict[str, Any]], xpath: str) -> Optional[str]:
        if not session:
            return None
        hints = session.get("hints")
        if not isinstance(hints, dict):
            return None
        value = hints.get(xpath)
        return value if isinstance(value, str) and value else None

    def _session_set_hint(self, session: Optional[Dict[str, Any]], xpath: str, frame_path: str):
        if not session or not xpath or not frame_path:
            return
        hints = session.get("hints")
        if isinstance(hints, dict):
            hints[xpath] = frame_path
        frames = session.get("frames")
        if isinstance(frames, list) and frame_path not in frames:
            frames.append(frame_path)

    def _session_add_miss(self, session: Optional[Dict[str, Any]], xpath: str):
        if not session or not xpath:
            return
        misses = session.get("misses")
        if isinstance(misses, set):
            misses.add(xpath)

    def _session_has_miss(self, session: Optional[Dict[str, Any]], xpath: str) -> bool:
        if not session:
            return False
        misses = session.get("misses")
        if not isinstance(misses, set):
            return False
        return xpath in misses

    def _try_find_in_frame(self, xpath: str, frame_path: str) -> Optional[Dict[str, Any]]:
        """?뱀젙 ?꾨젅?꾩뿉??XPath瑜?議고쉶?섍퀬 ?깃났 ??湲곕낯 寃곌낵瑜?諛섑솚."""
        try:
            with self.frame_context(frame_path):
                element = self.driver.find_element(By.XPATH, xpath)
                try:
                    count = len(self.driver.find_elements(By.XPATH, xpath))
                except Exception:
                    count = 1
                return {
                    "found": True,
                    "count": count,
                    "tag": element.tag_name,
                    "text": element.text[:50] if element.text else "",
                    "frame_path": frame_path,
                }
        except Exception:
            return None

    def get_windows(self) -> List[Dict]:
        """?대┛ ?덈룄??紐⑸줉 - ?앹뾽 ?곗꽑 ?뺣젹濡?議고쉶"""
        with self._lock:
            if not self.is_alive():
                return []

            windows = []
            current_handle = ""
            handles: List[str] = []
            try:
                current_handle = self.driver.current_window_handle
            except Exception as e:
                logger.debug(f"?꾩옱 ?덈룄???몃뱾 ?뺤씤 ?ㅽ뙣 (臾댁떆): {e}")
                pass

            try:
                handles = list(self.driver.window_handles)
            except Exception as e:
                logger.debug(f"?덈룄???몃뱾 議고쉶 ?ㅽ뙣: {e}")
                return []

            if not handles:
                return []

            if not self._root_window_handle or self._root_window_handle not in handles:
                self._root_window_handle = handles[0]

            for order, handle in enumerate(handles):
                try:
                    self.driver.switch_to.window(handle)
                    opener_exists = False
                    try:
                        opener_exists = bool(self.driver.execute_script("return !!window.opener;"))
                    except Exception:
                        opener_exists = False

                    is_popup = (handle != self._root_window_handle) or opener_exists
                    windows.append({
                        "handle": handle,
                        "title": self.driver.title,
                        "url": self.driver.current_url,
                        "current": (handle == current_handle),
                        "is_popup": is_popup,
                        "_order": order,
                    })
                except NoSuchWindowException:
                    continue
                except Exception as e:
                    logger.error(f"?덈룄???뺣낫 議고쉶 ?ㅽ뙣: {e}")

            # ?먮옒 ?덈룄?곕줈 蹂듦?
            if current_handle:
                try:
                    self.driver.switch_to.window(current_handle)
                except Exception as e:
                    logger.debug(f"?먮옒 ?덈룄??蹂듦? ?ㅽ뙣: {e}")
                    try:
                        fallback_handles = list(self.driver.window_handles)
                    except Exception:
                        fallback_handles = []
                    if fallback_handles:
                        self.driver.switch_to.window(fallback_handles[-1])

            windows.sort(
                key=lambda w: (
                    0 if w.get("is_popup") else 1,          # popup first
                    0 if w.get("current") else 1,           # current first within group
                    -int(w.get("_order", 0)),               # newest first
                )
            )

            for window in windows:
                window.pop("_order", None)

            return windows

    def switch_window(self, handle: str) -> bool:
        """?덈룄???꾪솚 - ?ㅽ뙣???泥??덈룄?곕줈 ?꾪솚"""
        with self._lock:
            try:
                self.driver.switch_to.window(handle)
                self._invalidate_frame_cache()
                return True
            except Exception as e:
                logger.error(f"?덈룄???꾪솚 ?ㅽ뙣: {e}")
                return self._recover_to_available_window()

    # -------------------------------------------------------------------------
    # Picker Script Injection
    # -------------------------------------------------------------------------

    def start_picker(self, overlay_mode: bool = False):
        """?붿냼 ?좏깮 紐⑤뱶 ?쒖옉 - 紐⑤뱺 ?덈룄???앹뾽 ?곗꽑) + iframe??二쇱엯"""
        with self._lock:
            self.ensure_valid_window()
            original_frame_path = self.current_frame_path
            try:
                current_handle = self.driver.current_window_handle
            except Exception:
                current_handle = ""

            try:
                handles = list(self.driver.window_handles)
            except Exception:
                handles = []

            if not handles:
                return

            if self._root_window_handle and self._root_window_handle in handles:
                scan_handles = [h for h in handles if h != self._root_window_handle] + [self._root_window_handle]
            else:
                scan_handles = handles

            injected_count = 0
            for handle in scan_handles:
                try:
                    self.driver.switch_to.window(handle)
                    self.driver.switch_to.default_content()
                    self.driver.execute_script(PICKER_SCRIPT)
                    injected_count += 1
                    self._inject_to_frames()
                except Exception as e:
                    logger.debug(f"?덈룄??picker 二쇱엯 ?ㅽ뙣({handle[:8]}...): {e}")

            if current_handle:
                try:
                    self.driver.switch_to.window(current_handle)
                    self.switch_to_frame_by_path(original_frame_path or "main")
                except Exception:
                    self._recover_to_available_window()

            logger.info(f"Picker injected windows={injected_count}")

    def _inject_to_frames(self, depth=0, max_depth=MAX_FRAME_DEPTH):
        if depth > max_depth:
            return

        try:
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
        except Exception:
            return  # iframe 寃???ㅽ뙣

        for frame in iframes:
            try:
                self.driver.switch_to.frame(frame)
                abort = False
                try:
                    # ?ㅽ겕由쏀듃 二쇱엯
                    try:
                        self.driver.execute_script(PICKER_SCRIPT)
                    except Exception:
                        pass  # 蹂댁븞 ?쒗븳 ?깆쑝濡??ㅽ뙣?????덉쓬

                    # ?ш? ?먯깋
                    self._inject_to_frames(depth + 1, max_depth)
                finally:
                    try:
                        self.driver.switch_to.parent_frame()
                    except Exception:
                        # parent_frame ?ㅽ뙣 ??而⑦뀓?ㅽ듃 ?ㅼ뿼 諛⑹?
                        try:
                            self.driver.switch_to.default_content()
                        except Exception:
                            pass
                        abort = True

                if abort:
                    return
            except Exception:
                continue

    def get_picker_result(self) -> Optional[Dict]:
        """Get picker result across windows (popup-first) and frames."""
        with self._lock:
            if not self.is_alive():
                return "CANCELLED"
            original_frame_path = self.current_frame_path
            try:
                current_handle = self.driver.current_window_handle
            except Exception:
                current_handle = ""

            try:
                handles = list(self.driver.window_handles)
            except Exception:
                handles = []

            if self._root_window_handle and self._root_window_handle in handles:
                scan_handles = [h for h in handles if h != self._root_window_handle] + [self._root_window_handle]
            else:
                scan_handles = handles

            try:
                for handle in scan_handles:
                    try:
                        self.driver.switch_to.window(handle)
                        self.driver.switch_to.default_content()

                        result = self.driver.execute_script("return window.__pickerResult;")
                        if result:
                            if isinstance(result, dict):
                                result["frame"] = "main"
                                result["window_handle"] = handle
                                result["window_title"] = self.driver.title
                                result["is_popup"] = bool(
                                    self._root_window_handle and handle != self._root_window_handle
                                )
                            return result

                        result = self._find_picker_result_in_frames()
                        if result and isinstance(result, dict):
                            result["window_handle"] = handle
                            result["window_title"] = self.driver.title
                            result["is_popup"] = bool(
                                self._root_window_handle and handle != self._root_window_handle
                            )
                            return result
                    except NoSuchWindowException:
                        continue
                    except Exception as e:
                        logger.debug(f"?덈룄??picker 寃곌낵 ?뺤씤 ?ㅽ뙣({handle[:8]}...): {e}")
                return None
            finally:
                if current_handle:
                    try:
                        self.driver.switch_to.window(current_handle)
                        self.switch_to_frame_by_path(original_frame_path or "main")
                    except Exception:
                        self._recover_to_available_window()

    def _find_picker_result_in_frames(self, path: str = "", depth: int = 0, max_depth: int = MAX_FRAME_DEPTH):
        """?꾨젅?꾩쓣 ?ш??곸쑝濡??먯깋?섏뿬 picker result瑜?李얠쓬 (??긽 parent_frame ?뺣━)"""
        if depth > max_depth:
            return None

        try:
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
        except Exception:
            return None

        for i, frame in enumerate(iframes):
            try:
                frame_id = frame.get_attribute("id") or frame.get_attribute("name") or f"index={i}"
                current_path = f"{path}/{frame_id}" if path else frame_id

                self.driver.switch_to.frame(frame)
                abort = False
                try:
                    result = self.driver.execute_script("return window.__pickerResult;")
                    if result:
                        if isinstance(result, dict):
                            result['frame'] = current_path
                        return result

                    found = self._find_picker_result_in_frames(current_path, depth + 1, max_depth)
                    if found:
                        # ?섏쐞?먯꽌 李얠? 寃쎌슦 frame 寃쎈줈媛 ?놁쑝硫?蹂닿컯
                        if isinstance(found, dict) and 'frame' not in found:
                            found['frame'] = current_path
                        return found
                finally:
                    try:
                        self.driver.switch_to.parent_frame()
                    except Exception:
                        try:
                            self.driver.switch_to.default_content()
                        except Exception:
                            pass
                        abort = True

                if abort:
                    return None
            except Exception:
                continue

        return None

    def is_picker_active(self) -> bool:
        """Check whether picker is active across windows and frames."""
        with self._lock:
            if not self.is_alive():
                return False
            original_frame_path = self.current_frame_path
            try:
                current_handle = self.driver.current_window_handle
            except Exception:
                current_handle = ""

            try:
                handles = list(self.driver.window_handles)
            except Exception:
                handles = []

            if self._root_window_handle and self._root_window_handle in handles:
                scan_handles = [h for h in handles if h != self._root_window_handle] + [self._root_window_handle]
            else:
                scan_handles = handles

            try:
                for handle in scan_handles:
                    try:
                        self.driver.switch_to.window(handle)
                        self.driver.switch_to.default_content()
                        active = self.driver.execute_script("return window.__pickerActive;")
                        if active:
                            return True
                        if self._check_active_in_frames():
                            return True
                    except NoSuchWindowException:
                        continue
                    except Exception:
                        continue
                return False
            finally:
                if current_handle:
                    try:
                        self.driver.switch_to.window(current_handle)
                        self.switch_to_frame_by_path(original_frame_path or "main")
                    except Exception:
                        self._recover_to_available_window()

    def _check_active_in_frames(self, depth: int = 0, max_depth: int = MAX_FRAME_DEPTH) -> bool:
        if depth > max_depth:
            return False

        try:
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
        except Exception:
            return False

        for frame in iframes:
            try:
                self.driver.switch_to.frame(frame)
                abort = False
                try:
                    if self.driver.execute_script("return window.__pickerActive;"):
                        return True
                    if self._check_active_in_frames(depth + 1, max_depth):
                        return True
                finally:
                    try:
                        self.driver.switch_to.parent_frame()
                    except Exception:
                        try:
                            self.driver.switch_to.default_content()
                        except Exception:
                            pass
                        abort = True

                if abort:
                    return False
            except Exception:
                continue

        return False
        
    def highlight(self, xpath: str, duration: int = 2500, frame_path: str = None) -> bool:
        """Highlight matched element, including nested iframe context."""
        with self.frame_context():
            self.ensure_valid_window()

            try:
                effective_frame = None
                if frame_path:
                    if self.switch_to_frame_by_path(frame_path):
                        effective_frame = frame_path
                    else:
                        effective_frame = None

                if not effective_frame:
                    _, found_path = self.find_element_in_all_frames(xpath)
                    if not found_path:
                        return False
                    effective_frame = found_path

                with self.frame_context(effective_frame):
                    try:
                        el = self.driver.find_element(By.XPATH, xpath)
                    except NoSuchElementException:
                        return False

                    # ?섏씠?쇱씠???ㅽ뻾
                    self.driver.execute_script("""
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
                    """, el, duration)

                return True

            except Exception as e:
                logger.error(f"?섏씠?쇱씠???ㅻ쪟: {e}")
                return False
            
    def validate_xpath(
        self,
        xpath: str,
        preferred_frame: Optional[str] = None,
        session: Optional[Dict[str, Any]] = None,
    ) -> Dict:
        """XPath 寃利?- ?몄뀡/?꾨젅???뚰듃瑜??쒖슜??以묒꺽 iframe ?먯깋."""
        with perf_span("browser.validate_xpath"):
            with self.frame_context():
                if not self.is_alive():
                    return {"found": False, "msg": "釉뚮씪?곗? ?곌껐 ?덈맖"}

                tried: Set[str] = set()
                candidate_frames: List[str] = []

                # 1) Try caller-provided preferred frame first.
                if preferred_frame:
                    candidate_frames.append(preferred_frame)

                # 2) ?몄뀡 ?뚰듃
                session_hint = self._session_get_hint(session, xpath)
                if session_hint and session_hint not in candidate_frames:
                    candidate_frames.append(session_hint)

                # 3) ?꾩뿭 ?뚰듃
                global_hint = self._get_xpath_frame_hint(xpath)
                if global_hint and global_hint not in candidate_frames:
                    candidate_frames.append(global_hint)

                for frame_path in candidate_frames:
                    tried.add(frame_path)
                    found = self._try_find_in_frame(xpath, frame_path)
                    if found:
                        self._set_xpath_frame_hint(xpath, frame_path)
                        self._session_set_hint(session, xpath, frame_path)
                        return found

                # 4) ?몄뀡 ?꾨젅???쒗쉶
                session_frames = session.get("frames") if isinstance(session, dict) else None
                if isinstance(session_frames, list):
                    for frame_path in session_frames:
                        if not frame_path or frame_path in tried:
                            continue
                        tried.add(frame_path)
                        found = self._try_find_in_frame(xpath, frame_path)
                        if found:
                            self._set_xpath_frame_hint(xpath, frame_path)
                            self._session_set_hint(session, xpath, frame_path)
                            return found

                # 5) ?몄뀡?먯꽌 ?대? miss 泥섎━??XPath???꾩닔 ?먯깋???앸왂
                if self._session_has_miss(session, xpath):
                    return {"found": False, "msg": "?붿냼瑜?李얠쓣 ???놁쓬"}

                # 6) 理쒗썑 ?섎떒: ?꾩껜 ?꾨젅???꾩닔 ?먯깋
                _, frame_path = self.find_element_in_all_frames(xpath, max_depth=MAX_FRAME_DEPTH)
                if not frame_path:
                    self._session_add_miss(session, xpath)
                    return {"found": False, "msg": "?붿냼瑜?李얠쓣 ???놁쓬"}

                found = self._try_find_in_frame(xpath, frame_path)
                if not found:
                    self._session_add_miss(session, xpath)
                    return {"found": False, "msg": "?붿냼瑜?李얠쓣 ???놁쓬"}

                self._set_xpath_frame_hint(xpath, frame_path)
                self._session_set_hint(session, xpath, frame_path)
                return found

    def _get_xpath_frame_hint(self, xpath: str) -> Optional[str]:
        """理쒓렐 ?깃났??XPath-?꾨젅???뚰듃 議고쉶 (TTL ?곸슜)."""
        hint = self._xpath_frame_hints.get(xpath)
        if not hint:
            return None
        frame_path, ts = hint
        if time.time() - ts > self.FRAME_CACHE_DURATION:
            self._xpath_frame_hints.pop(xpath, None)
            return None
        return frame_path

    def _set_xpath_frame_hint(self, xpath: str, frame_path: str):
        """XPath-?꾨젅???뚰듃 ???"""
        if not xpath or not frame_path:
            return
        self._xpath_frame_hints[xpath] = (frame_path, time.time())

    # =========================================================================
    # v4.0 ?좉퇋: ?ㅽ겕由곗꺑, ?붿냼 移댁슫?? ?곸꽭 ?뺣낫
    # =========================================================================
    
    def count_elements(self, xpath: str, frame_path: Optional[str] = None) -> int:
        """
        XPath??留ㅼ묶?섎뒗 紐⑤뱺 ?붿냼 媛쒖닔 諛섑솚 (?ㅼ떆媛?誘몃━蹂닿린??
        
        Args:
            xpath: 寃?됲븷 XPath
            frame_path: ?꾨젅??寃쎈줈 (None?대㈃ ?꾩옱 ?꾨젅??
        
        Returns:
            留ㅼ묶 ?붿냼 媛쒖닔 (?ㅻ쪟 ??-1)
        """
        with self.frame_context():
            if not self.is_alive():
                return -1

            try:
                if frame_path is not None:
                    with self.frame_context(frame_path):
                        return len(self.driver.find_elements(By.XPATH, xpath))
                return len(self.driver.find_elements(By.XPATH, xpath))
            except Exception as e:
                logger.debug(f"?붿냼 移댁슫???ㅽ뙣: {e}")
                return -1
    
    def get_element_info(
        self,
        xpath: str,
        frame_path: Optional[str] = None,
        include_attributes: bool = True,
        session: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict]:
        """
        ?붿냼???곸꽭 ?뺣낫 諛섑솚 (Diff 遺꾩꽍??
        
        Args:
            xpath: ?붿냼 XPath
            frame_path: ?꾨젅??寃쎈줈
        
        Returns:
            {
                'found': bool,
                'tag': str,
                'id': str,
                'name': str,
                'class': str,
                'text': str,
                'attributes': dict,
                'count': int,
                'parent_tag': str,
                'parent_id': str,
                'parent_class': str,
                'index': int
            }
        """
        with self.frame_context():
            if not self.is_alive():
                return {'found': False, 'msg': '釉뚮씪?곗? ?곌껐 ?덈맖'}

            try:
                resolved_frame = frame_path
                if resolved_frame is None:
                    hint = self._session_get_hint(session, xpath) or self._get_xpath_frame_hint(xpath)
                    if hint:
                        resolved_frame = hint
                    else:
                        _, found_path = self.find_element_in_all_frames(xpath, max_depth=MAX_FRAME_DEPTH)
                        if found_path:
                            resolved_frame = found_path

                if resolved_frame is not None and not self.switch_to_frame_by_path(resolved_frame):
                    return {'found': False, 'msg': f'?꾨젅???꾪솚 ?ㅽ뙣: {resolved_frame}'}

                try:
                    element = self.driver.find_element(By.XPATH, xpath)
                except NoSuchElementException:
                    return {'found': False, 'msg': '?붿냼瑜?李얠쓣 ???놁쓬'}

                info = {
                    'found': True,
                    'tag': element.tag_name.lower(),
                    'id': element.get_attribute('id') or '',
                    'name': element.get_attribute('name') or '',
                    'class': element.get_attribute('class') or '',
                    'text': (element.text[:100] if element.text else ''),
                    'count': len(self.driver.find_elements(By.XPATH, xpath)),
                    'frame_path': resolved_frame or 'main',
                }

                if include_attributes:
                    # 紐⑤뱺 ?띿꽦 ?섏쭛
                    try:
                        attrs_script = """
                        var el = arguments[0];
                        var attrs = {};
                        for (var i = 0; i < el.attributes.length; i++) {
                            var attr = el.attributes[i];
                            attrs[attr.name] = attr.value;
                        }
                        return attrs;
                        """
                        info['attributes'] = self.driver.execute_script(attrs_script, element)
                    except Exception:
                        info['attributes'] = {}
                else:
                    info['attributes'] = {}

                # 遺紐??뺣낫
                try:
                    parent_script = """
                    var el = arguments[0].parentElement;
                    if (!el) return null;
                    return {
                        tag: el.tagName.toLowerCase(),
                        id: el.id || '',
                        class: el.className || ''
                    };
                    """
                    parent_info = self.driver.execute_script(parent_script, element)
                    if parent_info:
                        info['parent_tag'] = parent_info.get('tag', '')
                        info['parent_id'] = parent_info.get('id', '')
                        info['parent_class'] = parent_info.get('class', '')
                except Exception:
                    info['parent_tag'] = ''
                    info['parent_id'] = ''
                    info['parent_class'] = ''

                # ?뺤젣 以??몃뜳??
                try:
                    index_script = """
                    var el = arguments[0];
                    var siblings = el.parentElement.children;
                    for (var i = 0; i < siblings.length; i++) {
                        if (siblings[i] === el) return i + 1;
                    }
                    return 0;
                    """
                    info['index'] = self.driver.execute_script(index_script, element)
                except Exception:
                    info['index'] = 0

                if resolved_frame:
                    self._set_xpath_frame_hint(xpath, resolved_frame)
                    self._session_set_hint(session, xpath, resolved_frame)
                return info

            except Exception as e:
                logger.error(f"?붿냼 ?뺣낫 議고쉶 ?ㅽ뙣: {e}")
                return {'found': False, 'msg': str(e)}
    
    def screenshot_element(self, xpath: str, save_path: str, frame_path: Optional[str] = None) -> bool:
        """
        ?붿냼 ?ㅽ겕由곗꺑 ???
        
        Args:
            xpath: ?붿냼 XPath
            save_path: ??ν븷 寃쎈줈 (.png)
            frame_path: ?꾨젅??寃쎈줈
        
        Returns:
            ?깃났 ?щ?
        """
        with self.frame_context():
            if not self.is_alive():
                return False

            try:
                if frame_path is not None:
                    if not self.switch_to_frame_by_path(frame_path):
                        return False

                try:
                    element = self.driver.find_element(By.XPATH, xpath)
                except NoSuchElementException:
                    logger.error(f"?ㅽ겕由곗꺑 ????붿냼 ?놁쓬: {xpath}")
                    return False

                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                time.sleep(0.3)

                element.screenshot(save_path)
                logger.info(f"?붿냼 ?ㅽ겕由곗꺑 ??? {save_path}")
                return True

            except Exception as e:
                logger.error(f"?ㅽ겕由곗꺑 ????ㅽ뙣: {e}")
                return False



