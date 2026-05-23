# -*- coding: utf-8 -*-
"""
XPath Explorer Code Generator
자동화 스크립트 생성 모듈
"""

from datetime import datetime
import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

from xpath_explorer.core.constants import XPATH_TEMPLATE_LIBRARY


class CodeTemplate(Enum):
    """코드 템플릿 종류"""

    SELENIUM_PYTHON = "selenium_python"
    PLAYWRIGHT_PYTHON = "playwright_python"
    PYAUTOGUI = "pyautogui"


@dataclass
class ActionStep:
    """자동화 액션 단계"""

    action: str  # click, type, wait, scroll
    xpath: str
    value: str = ""  # type 액션의 입력값
    wait_time: float = 1.0
    description: str = ""


@dataclass(frozen=True)
class XPathTemplate:
    """Reusable XPath template entry."""

    name: str
    category: str
    xpath: str
    description: str = ""


class CodeGenerator:
    """XPath 기반 자동화 코드 생성기"""

    def __init__(self):
        self.indent = "    "

    @staticmethod
    def list_xpath_templates(category: str = "", keyword: str = "") -> List[XPathTemplate]:
        """Return XPath templates with optional category/keyword filtering."""
        category = (category or "").strip().lower()
        keyword = (keyword or "").strip().lower()
        templates: List[XPathTemplate] = []

        for raw in XPATH_TEMPLATE_LIBRARY:
            if not isinstance(raw, dict):
                continue
            name = str(raw.get("name") or "").strip()
            item_category = str(raw.get("category") or "").strip()
            xpath = str(raw.get("xpath") or "").strip()
            description = str(raw.get("description") or "").strip()
            if not name or not item_category or not xpath:
                continue

            if category and item_category.lower() != category:
                continue
            if keyword:
                haystack = f"{name} {item_category} {xpath} {description}".lower()
                if keyword not in haystack:
                    continue

            templates.append(
                XPathTemplate(
                    name=name,
                    category=item_category,
                    xpath=xpath,
                    description=description,
                )
            )

        templates.sort(key=lambda t: (t.category, t.name))
        return templates

    def generate(self, items: List, template: CodeTemplate, actions: Optional[List[ActionStep]] = None) -> str:
        """
        XPath 항목들로 자동화 코드 생성

        Args:
            items: XPathItem 목록
            template: 코드 템플릿 종류
            actions: 액션 단계 목록 (없으면 기본 click 액션)
        """
        if template == CodeTemplate.SELENIUM_PYTHON:
            return self._generate_selenium(items, actions)
        if template == CodeTemplate.PLAYWRIGHT_PYTHON:
            return self._generate_playwright(items, actions)
        if template == CodeTemplate.PYAUTOGUI:
            return self._generate_pyautogui(items, actions)
        return "# Unsupported template"

    def _generate_selenium(self, items: List, actions: Optional[List[ActionStep]] = None) -> str:
        """Selenium Python 코드 생성"""
        item_constants = self._build_item_constants(items)
        xpath_name_map = self._build_xpath_name_map_from_constants(item_constants)

        code = '''# -*- coding: utf-8 -*-
"""
자동 생성된 Selenium 자동화 스크립트
생성 시간: __TIMESTAMP__
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time


class XPathConstants:
    """XPath 상수 정의"""
'''
        for item, safe_name in item_constants:
            xpath_literal = self._python_literal(getattr(item, "xpath", ""))
            comment = self._sanitize_comment(getattr(item, "description", ""))
            code += f"{self.indent}{safe_name} = {xpath_literal}  # {comment}\n"

        code += "\n"
        code += f"{self.indent}ITEM_CONTEXTS = {{\n"
        for item, safe_name in item_constants:
            context_literal = self._python_literal_dict(self._item_context(item))
            code += f"{self.indent * 2}{self._python_literal(safe_name)}: {context_literal},\n"
        code += f"{self.indent}}}\n"

        code += '''

class AutomationScript:
    """자동화 스크립트"""

    def __init__(self, driver=None):
        self.driver = driver or webdriver.Chrome()
        self.wait = WebDriverWait(self.driver, 10)

    def _switch_window_context(self, context: dict):
        title = context.get("window_title") or ""
        url = context.get("window_url") or ""
        if not title and not url:
            return
        original = self.driver.current_window_handle
        for handle in self.driver.window_handles:
            self.driver.switch_to.window(handle)
            if (title and self.driver.title == title) or (url and self.driver.current_url == url):
                return
        self.driver.switch_to.window(original)

    def _switch_frame_context(self, context: dict):
        frame_path = context.get("frame_path") or ""
        self.driver.switch_to.default_content()
        if not frame_path or frame_path == "main":
            return
        for part in frame_path.split("/"):
            if part.startswith("index="):
                index = int(part.split("=", 1)[1])
                frames = self.driver.find_elements(By.TAG_NAME, "iframe")
                self.driver.switch_to.frame(frames[index])
            else:
                self.driver.switch_to.frame(part)

    def _apply_context(self, context: dict | None):
        if not context:
            return
        self._switch_window_context(context)
        self._switch_frame_context(context)

    def find_element(self, xpath: str, timeout: int = 10, context: dict | None = None):
        """요소 찾기 (대기 포함)"""
        try:
            self._apply_context(context)
            return self.wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
        except TimeoutException:
            print("요소를 찾을 수 없습니다: %s" % xpath)
            return None

    def click_element(self, xpath: str, context: dict | None = None):
        """요소 클릭"""
        elem = self.find_element(xpath, context=context)
        if elem:
            elem.click()
            time.sleep(0.5)
            return True
        return False

    def type_text(self, xpath: str, text: str, context: dict | None = None):
        """텍스트 입력"""
        elem = self.find_element(xpath, context=context)
        if elem:
            elem.clear()
            elem.send_keys(text)
            return True
        return False

    def run_sequence(self):
        """자동화 시퀀스 실행"""
'''
        code += self._render_python_actions(actions, xpath_name_map, for_playwright=False)
        code += '''

if __name__ == "__main__":
    script = AutomationScript()
    script.run_sequence()
'''
        return code.replace("__TIMESTAMP__", self._timestamp())

    def _generate_playwright(self, items: List, actions: Optional[List[ActionStep]] = None) -> str:
        """Playwright Python 코드 생성"""
        item_constants = self._build_item_constants(items)
        xpath_name_map = self._build_xpath_name_map_from_constants(item_constants)

        code = '''# -*- coding: utf-8 -*-
"""
자동 생성된 Playwright 자동화 스크립트
생성 시간: __TIMESTAMP__
"""

from playwright.sync_api import sync_playwright
import time


class XPathConstants:
    """XPath 상수 정의"""
'''
        for item, safe_name in item_constants:
            xpath_literal = self._python_literal(getattr(item, "xpath", ""))
            comment = self._sanitize_comment(getattr(item, "description", ""))
            code += f"{self.indent}{safe_name} = {xpath_literal}  # {comment}\n"

        code += "\n"
        code += f"{self.indent}ITEM_CONTEXTS = {{\n"
        for item, safe_name in item_constants:
            context_literal = self._python_literal_dict(self._item_context(item))
            code += f"{self.indent * 2}{self._python_literal(safe_name)}: {context_literal},\n"
        code += f"{self.indent}}}\n"

        code += '''

class AutomationScript:
    """Playwright 자동화 스크립트"""

    def __init__(self):
        self.playwright = None
        self.browser = None
        self.page = None

    def start(self, url: str = "about:blank", headless: bool = False):
        """브라우저 시작"""
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=headless)
        self.page = self.browser.new_page()
        self.page.goto(url)

    def close(self):
        """브라우저 종료"""
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def _select_context(self, context: dict | None):
        if not context:
            return self.page
        target = self.page
        title = context.get("window_title") or ""
        url = context.get("window_url") or ""
        if title or url:
            for candidate in self.page.context.pages:
                if (title and candidate.title() == title) or (url and candidate.url == url):
                    target = candidate
                    break
        frame_path = context.get("frame_path") or ""
        if not frame_path or frame_path == "main":
            return target
        frame = target.main_frame
        for part in frame_path.split("/"):
            children = list(frame.child_frames)
            if part.startswith("index="):
                frame = children[int(part.split("=", 1)[1])]
                continue
            match = None
            for child in children:
                if child.name == part or part in child.url:
                    match = child
                    break
            if match is None:
                raise RuntimeError("프레임을 찾을 수 없습니다: %s" % part)
            frame = match
        return frame

    def click_element(self, xpath: str, timeout: int = 10000, context: dict | None = None):
        """요소 클릭"""
        try:
            target = self._select_context(context)
            target.locator(f"xpath={xpath}").click(timeout=timeout)
            return True
        except Exception as e:
            print("클릭 실패: %s" % e)
            return False

    def fill_text(self, xpath: str, text: str, context: dict | None = None):
        """텍스트 입력"""
        try:
            target = self._select_context(context)
            target.locator(f"xpath={xpath}").fill(text)
            return True
        except Exception as e:
            print("입력 실패: %s" % e)
            return False

    def run_sequence(self):
        """자동화 시퀀스 실행"""
'''
        code += self._render_python_actions(actions, xpath_name_map, for_playwright=True)
        code += '''

if __name__ == "__main__":
    script = AutomationScript()
    try:
        script.start("https://example.com")
        script.run_sequence()
    finally:
        script.close()
'''
        return code.replace("__TIMESTAMP__", self._timestamp())

    def _generate_pyautogui(self, items: List, actions: Optional[List[ActionStep]] = None) -> str:
        """PyAutoGUI 코드 생성 (XPath 참조용 주석 포함)"""
        code = '''# -*- coding: utf-8 -*-
"""
자동 생성된 PyAutoGUI 매크로 스크립트
생성 시간: __TIMESTAMP__

주의: PyAutoGUI는 화면 좌표 기반이므로 XPath는 참조용입니다.
실제 좌표는 수동으로 조정해야 합니다.
"""

import pyautogui
import time

# 안전 설정
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.5


# XPath 참조 (좌표 매핑용 주석)
XPATH_REFERENCES = {
'''
        for item in items:
            key_literal = self._python_literal(getattr(item, "name", "unnamed"))
            xpath_literal = self._python_literal(getattr(item, "xpath", ""))
            comment = self._sanitize_comment(getattr(item, "description", ""))
            code += f"{self.indent}{key_literal}: {xpath_literal},  # {comment}\n"

        code += '''}


def click_at(x: int, y: int, description: str = ""):
    """지정 좌표 클릭"""
    print(f"클릭: {description} ({x}, {y})")
    pyautogui.click(x, y)
    time.sleep(0.3)


def type_text(text: str, interval: float = 0.05):
    """텍스트 입력"""
    pyautogui.typewrite(text, interval=interval)


def run_macro():
    """매크로 실행"""
    print("3초 후 매크로 시작...")
    time.sleep(3)

    # 여기에 좌표 기반 액션을 작성하세요
    # 예: click_at(100, 200, "로그인 버튼")
    pass


if __name__ == "__main__":
    run_macro()
'''
        return code.replace("__TIMESTAMP__", self._timestamp())

    def _render_python_actions(
        self,
        actions: Optional[List[ActionStep]],
        xpath_name_map: Dict[str, str],
        for_playwright: bool,
    ) -> str:
        if not actions:
            return f"{self.indent * 2}# 여기에 자동화 로직을 작성하세요\n{self.indent * 2}pass\n"

        lines = []
        for step in actions:
            action = (step.action or "").lower().strip()
            target_expr = self._resolve_python_xpath_expr(step.xpath, xpath_name_map)
            comment = self._sanitize_comment(step.description or step.xpath or step.action)

            if action == "click":
                lines.append(f"{self.indent * 2}# {comment}")
                context_expr = self._resolve_python_context_expr(step.xpath, xpath_name_map)
                lines.append(f"{self.indent * 2}self.click_element({target_expr}, context={context_expr})")
            elif action == "type":
                value_literal = self._python_literal(step.value)
                lines.append(f"{self.indent * 2}# {comment}")
                if for_playwright:
                    context_expr = self._resolve_python_context_expr(step.xpath, xpath_name_map)
                    lines.append(f"{self.indent * 2}self.fill_text({target_expr}, {value_literal}, context={context_expr})")
                else:
                    context_expr = self._resolve_python_context_expr(step.xpath, xpath_name_map)
                    lines.append(f"{self.indent * 2}self.type_text({target_expr}, {value_literal}, context={context_expr})")
            elif action == "wait":
                lines.append(f"{self.indent * 2}# {comment}")
                lines.append(f"{self.indent * 2}time.sleep({max(0.0, float(step.wait_time))})")

        if not lines:
            return f"{self.indent * 2}# 여기에 자동화 로직을 작성하세요\n{self.indent * 2}pass\n"
        return "\n".join(lines) + "\n"

    def _build_item_constants(self, items: List) -> List[tuple[object, str]]:
        constants = []
        used_names: Dict[str, int] = {}
        for item in items:
            raw_safe_name = self._safe_var_name(getattr(item, "name", "unnamed"))
            suffix = used_names.get(raw_safe_name, 0)
            used_names[raw_safe_name] = suffix + 1
            safe_name = raw_safe_name if suffix == 0 else f"{raw_safe_name}_{suffix + 1}"
            constants.append((item, safe_name))
        return constants

    def _build_xpath_name_map_from_constants(self, item_constants: List[tuple[object, str]]) -> Dict[str, str]:
        mapping: Dict[str, str] = {}
        for item, safe_name in item_constants:
            xpath = getattr(item, "xpath", "")
            if xpath and xpath not in mapping:
                mapping[xpath] = safe_name
        return mapping

    def _build_xpath_name_map(self, items: List) -> Dict[str, str]:
        return self._build_xpath_name_map_from_constants(self._build_item_constants(items))

    def _resolve_python_xpath_expr(self, xpath: str, xpath_name_map: Dict[str, str]) -> str:
        const_name = xpath_name_map.get(xpath or "")
        if const_name:
            return f"XPathConstants.{const_name}"
        return self._python_literal(xpath or "")

    def _resolve_python_context_expr(self, xpath: str, xpath_name_map: Dict[str, str]) -> str:
        const_name = xpath_name_map.get(xpath or "")
        if const_name:
            return f"XPathConstants.ITEM_CONTEXTS.get({self._python_literal(const_name)})"
        return "None"

    def _item_context(self, item) -> Dict[str, str]:
        return {
            "frame_path": str(getattr(item, "found_frame", "") or ""),
            "window_title": str(getattr(item, "found_window_title", "") or ""),
            "window_url": str(getattr(item, "found_window_url", "") or ""),
            "source_engine": str(getattr(item, "source_engine", "") or ""),
        }

    def _timestamp(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _sanitize_comment(self, text: str) -> str:
        return (text or "").replace("\n", " ").replace("\r", " ").strip()

    def _python_literal(self, value: str) -> str:
        return json.dumps(value or "", ensure_ascii=False)

    def _python_literal_dict(self, value: Dict[str, str]) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    def _safe_var_name(self, name: str) -> str:
        """안전한 변수명으로 변환"""
        safe = re.sub(r"[^a-zA-Z0-9가-힣_]", "_", name or "")
        if safe and safe[0].isdigit():
            safe = "_" + safe
        return safe.upper() if safe else "UNNAMED"
