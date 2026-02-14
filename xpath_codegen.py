# -*- coding: utf-8 -*-
"""
XPath Explorer Code Generator
자동화 스크립트 생성 모듈
"""

from typing import List, Dict
from dataclasses import dataclass
from enum import Enum


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


class CodeGenerator:
    """XPath 기반 자동화 코드 생성기"""
    
    def __init__(self):
        self.indent = "    "
    
    def generate(self, items: List, template: CodeTemplate, actions: List[ActionStep] = None) -> str:
        """
        XPath 항목들로 자동화 코드 생성
        
        Args:
            items: XPathItem 목록
            template: 코드 템플릿 종류
            actions: 액션 단계 목록 (없으면 기본 click 액션)
        """
        if template == CodeTemplate.SELENIUM_PYTHON:
            return self._generate_selenium(items, actions)
        elif template == CodeTemplate.PLAYWRIGHT_PYTHON:
            return self._generate_playwright(items, actions)
        elif template == CodeTemplate.PYAUTOGUI:
            return self._generate_pyautogui(items, actions)
        else:
            return "# Unsupported template"
    
    def _generate_selenium(self, items: List, actions: List[ActionStep] = None) -> str:
        """Selenium Python 코드 생성"""
        code = '''# -*- coding: utf-8 -*-
"""
자동 생성된 Selenium 자동화 스크립트
생성 시간: {timestamp}
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
        # XPath 상수 생성
        for item in items:
            safe_name = self._safe_var_name(item.name)
            code += f'{self.indent}{safe_name} = "{item.xpath}"  # {item.description}\n'
        
        code += '''

class AutomationScript:
    """자동화 스크립트"""
    
    def __init__(self, driver=None):
        self.driver = driver or webdriver.Chrome()
        self.wait = WebDriverWait(self.driver, 10)
    
    def find_element(self, xpath: str, timeout: int = 10):
        """요소 찾기 (대기 포함)"""
        try:
            return self.wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
        except TimeoutException:
            print(f"요소를 찾을 수 없습니다: {xpath}")
            return None
    
    def click_element(self, xpath: str):
        """요소 클릭"""
        elem = self.find_element(xpath)
        if elem:
            elem.click()
            time.sleep(0.5)
            return True
        return False
    
    def type_text(self, xpath: str, text: str):
        """텍스트 입력"""
        elem = self.find_element(xpath)
        if elem:
            elem.clear()
            elem.send_keys(text)
            return True
        return False
    
    def run_sequence(self):
        """자동화 시퀀스 실행"""
'''
        # 액션 시퀀스 생성
        if actions:
            for step in actions:
                safe_name = self._safe_var_name(step.description or "element")
                if step.action == "click":
                    code += f'{self.indent * 2}self.click_element(XPathConstants.{safe_name})  # {step.description}\n'
                elif step.action == "type":
                    code += f'{self.indent * 2}self.type_text(XPathConstants.{safe_name}, "{step.value}")\n'
                elif step.action == "wait":
                    code += f'{self.indent * 2}time.sleep({step.wait_time})\n'
        else:
            code += f'{self.indent * 2}# 여기에 자동화 로직을 작성하세요\n'
            code += f'{self.indent * 2}pass\n'
        
        code += '''

if __name__ == "__main__":
    script = AutomationScript()
    script.run_sequence()
'''
        from datetime import datetime
        return code.format(timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    def _generate_playwright(self, items: List, actions: List[ActionStep] = None) -> str:
        """Playwright Python 코드 생성"""
        code = '''# -*- coding: utf-8 -*-
"""
자동 생성된 Playwright 자동화 스크립트
생성 시간: {timestamp}
"""

from playwright.sync_api import sync_playwright, Page
import time


class XPathConstants:
    """XPath 상수 정의"""
'''
        for item in items:
            safe_name = self._safe_var_name(item.name)
            code += f'{self.indent}{safe_name} = "{item.xpath}"  # {item.description}\n'
        
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
    
    def click_element(self, xpath: str, timeout: int = 10000):
        """요소 클릭"""
        try:
            self.page.locator(f"xpath={xpath}").click(timeout=timeout)
            return True
        except Exception as e:
            print(f"클릭 실패: {e}")
            return False
    
    def fill_text(self, xpath: str, text: str):
        """텍스트 입력"""
        try:
            self.page.locator(f"xpath={xpath}").fill(text)
            return True
        except Exception as e:
            print(f"입력 실패: {e}")
            return False
    
    def run_sequence(self):
        """자동화 시퀀스 실행"""
'''
        if actions:
            for step in actions:
                safe_name = self._safe_var_name(step.description or "element")
                if step.action == "click":
                    code += f'{self.indent * 2}self.click_element(XPathConstants.{safe_name})\n'
                elif step.action == "type":
                    code += f'{self.indent * 2}self.fill_text(XPathConstants.{safe_name}, "{step.value}")\n'
                elif step.action == "wait":
                    code += f'{self.indent * 2}time.sleep({step.wait_time})\n'
        else:
            code += f'{self.indent * 2}# 여기에 자동화 로직을 작성하세요\n'
            code += f'{self.indent * 2}pass\n'
        
        code += '''

if __name__ == "__main__":
    script = AutomationScript()
    try:
        script.start("https://example.com")
        script.run_sequence()
    finally:
        script.close()
'''
        from datetime import datetime
        return code.format(timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    def _generate_pyautogui(self, items: List, actions: List[ActionStep] = None) -> str:
        """PyAutoGUI 코드 생성 (XPath 참조용 주석 포함)"""
        code = '''# -*- coding: utf-8 -*-
"""
자동 생성된 PyAutoGUI 매크로 스크립트
생성 시간: {timestamp}

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
            code += f'{self.indent}"{item.name}": "{item.xpath}",  # {item.description}\n'
        
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
        from datetime import datetime
        return code.format(timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    def _safe_var_name(self, name: str) -> str:
        """안전한 변수명으로 변환"""
        import re
        # 공백, 특수문자를 언더스코어로
        safe = re.sub(r'[^a-zA-Z0-9가-힣_]', '_', name)
        # 숫자로 시작하면 앞에 언더스코어
        if safe and safe[0].isdigit():
            safe = '_' + safe
        return safe.upper() if safe else 'UNNAMED'
