#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
티켓 사이트 XPath 탐색기 v3.2 (Refactored)
- 직관적인 UI/UX
- 실시간 요소 선택 및 XPath 추출
- 다중 사이트 프리셋 (인터파크, 멜론티켓, YES24, 티켓링크)
- 다중 윈도우/팝업 지원
- 다양한 내보내기 형식
- 향상된 안정성 및 예외 처리
"""

import sys
import os
import json
import time
import random
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any, Tuple
from pathlib import Path

# HiDPI 지원을 위한 환경변수 설정 (PyQt6 초기화 전에 설정)
os.environ['QT_ENABLE_HIGHDPI_SCALING'] = '1'
os.environ['QT_SCALE_FACTOR_ROUNDING_POLICY'] = 'PassThrough'

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit, QComboBox, QCheckBox,
    QTableWidget, QTableWidgetItem, QTabWidget, QSplitter, QGroupBox,
    QProgressBar, QMenu, QToolBar, QDialog, QDialogButtonBox,
    QListWidget, QListWidgetItem, QMessageBox, QFileDialog, QHeaderView,
    QAbstractItemView, QSpinBox, QFormLayout, QScrollArea, QFrame,
    QTreeWidget, QTreeWidgetItem, QPlainTextEdit, QStackedWidget,
    QToolButton, QGridLayout, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize, QSettings, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QColor, QAction, QPalette, QIcon, QPixmap, QShortcut, QKeySequence

# Selenium
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

# ============================================================================
# 로깅 설정
# ============================================================================

import logging
from logging.handlers import RotatingFileHandler

def setup_logger():
    """로거 설정"""
    logger = logging.getLogger('XPathExplorer')
    logger.setLevel(logging.DEBUG)
    
    # 콘솔 핸들러
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S')
    console_handler.setFormatter(console_format)
    
    # 파일 핸들러
    log_dir = Path.home() / '.xpath_explorer'
    log_dir.mkdir(exist_ok=True)
    file_handler = RotatingFileHandler(
        log_dir / 'debug.log',
        maxBytes=5*1024*1024,
        backupCount=3,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter('%(asctime)s [%(levelname)s] %(funcName)s:%(lineno)d - %(message)s')
    file_handler.setFormatter(file_format)
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger

logger = setup_logger()


# ============================================================================
# 설정 상수
# ============================================================================

class Config:
    """앱 설정 상수"""
    APP_NAME = "티켓 사이트 XPath 탐색기"
    VERSION = "3.3"  # HiDPI 지원 추가
    WINDOW_WIDTH = 1600
    WINDOW_HEIGHT = 950
    CHECK_INTERVAL_MS = 2000
    MAX_HISTORY = 50
    TOAST_DURATION_MS = 3000
    THREAD_TIMEOUT_MS = 2000
    FONT_SIZE_MIN = 8
    FONT_SIZE_MAX = 18
    FONT_SIZE_DEFAULT = 10
    # HiDPI 기준 DPI (100% 스케일링)
    BASE_DPI = 96


# ============================================================================
# DPI 스케일링 헬퍼
# ============================================================================

def get_dpi_scale() -> float:
    """현재 화면의 DPI 스케일 비율을 반환합니다."""
    app = QApplication.instance()
    if app:
        screen = app.primaryScreen()
        if screen:
            return screen.logicalDotsPerInch() / Config.BASE_DPI
    return 1.0

def scaled(value: int) -> int:
    """픽셀 값을 현재 DPI에 맞게 스케일링합니다."""
    return int(value * get_dpi_scale())

def scaled_size(width: int, height: int) -> tuple:
    """크기 값을 현재 DPI에 맞게 스케일링합니다."""
    scale = get_dpi_scale()
    return (int(width * scale), int(height * scale))


# ============================================================================
# Toast 알림 위젯
# ============================================================================

class ToastWidget(QFrame):
    """화면 상단에 표시되는 toast 알림"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                border-radius: 10px;
                padding: 15px 25px;
                font-size: 11pt;
                font-weight: bold;
            }
        """)
        # DPI 스케일링 적용
        self.setFixedHeight(scaled(50))
        self.setMinimumWidth(scaled(300))
        self.setMaximumWidth(scaled(600))
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(scaled(15), scaled(5), scaled(15), scaled(5))
        
        self.icon_label = QLabel()
        layout.addWidget(self.icon_label)
        
        self.message_label = QLabel()
        self.message_label.setStyleSheet("border: none; background: transparent;")
        layout.addWidget(self.message_label, 1)
        
        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(scaled(25), scaled(25))
        self.close_btn.setStyleSheet("border: none; background: transparent; font-size: 14pt;")
        self.close_btn.clicked.connect(self.hide)
        layout.addWidget(self.close_btn)
        
        self.hide()
        
        self._timer = QTimer()
        self._timer.timeout.connect(self._fade_out)
    
    def show_toast(self, message: str, toast_type: str = "info", duration: int = 3000):
        """
        Toast 메시지 표시
        
        Args:
            message: 표시할 메시지
            toast_type: "success", "warning", "error", "info"
            duration: 표시 시간 (ms), 0이면 자동 닫힘 없음
        """
        styles = {
            "success": ("#06d6a0", "#0d1b2a", "✅"),
            "warning": ("#ffd166", "#0d1b2a", "⚠️"),
            "error": ("#ef476f", "#ffffff", "❌"),
            "info": ("#00d4ff", "#0d1b2a", "ℹ️"),
        }
        
        bg_color, text_color, icon = styles.get(toast_type, styles["info"])
        
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border-radius: 10px;
                padding: 15px 25px;
            }}
        """)
        self.icon_label.setText(icon)
        self.icon_label.setStyleSheet(f"color: {text_color}; border: none; background: transparent; font-size: 14pt;")
        self.message_label.setText(message)
        self.message_label.setStyleSheet(f"color: {text_color}; border: none; background: transparent;")
        self.close_btn.setStyleSheet(f"color: {text_color}; border: none; background: transparent;")
        
        # 부모 위젯 중앙 상단에 배치
        if self.parent():
            parent_rect = self.parent().rect()
            self.move((parent_rect.width() - self.width()) // 2, scaled(10))
            self.raise_()
        
        self.show()
        
        if duration > 0:
            self._timer.start(duration)
    
    def _fade_out(self):
        self._timer.stop()
        self.hide()


# ============================================================================
# 사이트 프리셋 정의
# ============================================================================


SITE_PRESETS = {
    "인터파크": {
        "name": "인터파크 티켓",
        "url": "https://tickets.interpark.com",
        "login_url": "https://accounts.interpark.com/login",
        "description": "인터파크 티켓 예매",
        "items": [
            # 로그인
            {"name": "login_button", "xpath": '//*[@id="__next"]/div/div/div/div[2]/div[1]/div/div/div/div/div[2]/div/button', "category": "login", "desc": "메인 로그인 버튼"},
            {"name": "login_id", "xpath": 'userId', "category": "login", "desc": "ID 입력 (ID속성)"},
            {"name": "login_pw", "xpath": 'userPwd', "category": "login", "desc": "PW 입력 (ID속성)"},
            {"name": "login_submit", "xpath": 'btn_login', "category": "login", "desc": "로그인 버튼 (ID속성)"},
            # 예매
            {"name": "book_button", "xpath": '//*[@id="productSide"]/div/div[2]/a[contains(@class, "is-primary")]', "category": "booking", "desc": "예매하기 버튼"},
            {"name": "book_button_alt", "xpath": '//a[contains(text(), "예매하기")]', "category": "booking", "desc": "예매 버튼 (텍스트)"},
            {"name": "date_area", "xpath": '//*[@id="productSide"]/div/div[1]', "category": "booking", "desc": "날짜 선택 영역"},
            {"name": "round_list", "xpath": '//ul[contains(@class, "roundList")]/li', "category": "booking", "desc": "회차 목록"},
            # 좌석
            {"name": "seat_iframe", "xpath": "//*[@id='ifrmSeat']", "category": "seat", "desc": "좌석 iframe"},
            {"name": "seat_detail_frame", "xpath": "ifrmSeatDetail", "category": "seat", "desc": "좌석상세 iframe (name)"},
            {"name": "seat_area", "xpath": '//*[@id="divSeatArray"]', "category": "seat", "desc": "좌석 배열"},
            {"name": "seat_grade", "xpath": '//*[@id="divGrade"]', "category": "seat", "desc": "좌석 등급"},
            {"name": "next_step", "xpath": 'NextStepImage', "category": "seat", "desc": "다음단계 (ID)"},
            {"name": "seat_confirm", "xpath": '//*[@id="btnConfirm"]', "category": "seat", "desc": "좌석 확인"},
            # 캡차
            {"name": "captcha_img", "xpath": "//*[@id='imgCaptcha']", "category": "captcha", "desc": "캡차 이미지"},
            {"name": "captcha_input", "xpath": "txtCaptcha", "category": "captcha", "desc": "캡차 입력 (ID)"},
            {"name": "captcha_confirm", "xpath": "/html/body/div[2]/div[1]/div[4]/a[2]", "category": "captcha", "desc": "캡차 확인"},
            {"name": "captcha_reload", "xpath": "/html/body/div[2]/div[1]/div[1]/a[1]", "category": "captcha", "desc": "캡차 새로고침"},
            # 구역
            {"name": "district_tmpl", "xpath": '/html/body/form[1]/div/div[1]/div[3]/div/div[1]/div/div/div/div/table/tbody/tr[{n}]/td[1]/div/span[2]', "category": "district", "desc": "구역 템플릿"},
            {"name": "sub_district", "xpath": "/html/body/form[1]/div/div[1]/div[3]/div/div[1]/div/div/div/div/table/tbody/tr[{n}]/td/div/ul/li[{i}]/a", "category": "district", "desc": "하위구역 템플릿"},
        ]
    },
    "멜론티켓": {
        "name": "멜론티켓",
        "url": "https://ticket.melon.com",
        "login_url": "https://member.melon.com/login",
        "description": "멜론티켓 예매",
        "items": [
            {"name": "login_id", "xpath": '//*[@id="id"]', "category": "login", "desc": "ID 입력"},
            {"name": "login_pw", "xpath": '//*[@id="pwd"]', "category": "login", "desc": "PW 입력"},
            {"name": "login_submit", "xpath": '//*[@id="btnLogin"]', "category": "login", "desc": "로그인 버튼"},
            {"name": "book_button", "xpath": '//a[contains(@class, "btn_book")]', "category": "booking", "desc": "예매하기"},
            {"name": "date_select", "xpath": '//div[contains(@class, "date_select")]', "category": "booking", "desc": "날짜 선택"},
            {"name": "time_select", "xpath": '//ul[contains(@class, "time_list")]/li', "category": "booking", "desc": "시간 선택"},
            {"name": "seat_frame", "xpath": '//iframe[contains(@id, "seat")]', "category": "seat", "desc": "좌석 iframe"},
            {"name": "seat_area", "xpath": '//*[@id="seatArea"]', "category": "seat", "desc": "좌석 영역"},
            {"name": "next_btn", "xpath": '//button[contains(text(), "다음")]', "category": "seat", "desc": "다음 버튼"},
        ]
    },
    "YES24": {
        "name": "YES24 티켓",
        "url": "https://ticket.yes24.com",
        "login_url": "https://www.yes24.com/Templates/FTLogin.aspx",
        "description": "YES24 티켓 예매",
        "items": [
            {"name": "login_id", "xpath": '//*[@id="SMemberID"]', "category": "login", "desc": "ID 입력"},
            {"name": "login_pw", "xpath": '//*[@id="SMemberPassword"]', "category": "login", "desc": "PW 입력"},
            {"name": "login_submit", "xpath": '//*[@id="btnLogin"]', "category": "login", "desc": "로그인"},
            {"name": "book_button", "xpath": '//a[contains(@class, "btn_reserve")]', "category": "booking", "desc": "예매하기"},
            {"name": "calendar", "xpath": '//div[contains(@class, "calendar")]', "category": "booking", "desc": "캘린더"},
            {"name": "time_list", "xpath": '//ul[@class="time-list"]/li', "category": "booking", "desc": "시간 목록"},
            {"name": "seat_iframe", "xpath": '//iframe[@name="ifrmSeat"]', "category": "seat", "desc": "좌석 iframe"},
            {"name": "grade_list", "xpath": '//div[@class="grade-list"]//li', "category": "seat", "desc": "등급 목록"},
            {"name": "confirm_btn", "xpath": '//button[contains(text(), "선택완료")]', "category": "seat", "desc": "선택완료"},
        ]
    },
    "티켓링크": {
        "name": "티켓링크",
        "url": "https://www.ticketlink.co.kr",
        "login_url": "https://www.ticketlink.co.kr/login",
        "description": "티켓링크 예매",
        "items": [
            {"name": "login_id", "xpath": '//*[@id="userId"]', "category": "login", "desc": "ID 입력"},
            {"name": "login_pw", "xpath": '//*[@id="userPwd"]', "category": "login", "desc": "PW 입력"},
            {"name": "login_submit", "xpath": '//button[@type="submit"]', "category": "login", "desc": "로그인"},
            {"name": "book_button", "xpath": '//a[contains(@class, "btn_book")]', "category": "booking", "desc": "예매"},
            {"name": "date_picker", "xpath": '//div[contains(@class, "datepicker")]', "category": "booking", "desc": "날짜"},
            {"name": "seat_frame", "xpath": '//iframe[contains(@src, "seat")]', "category": "seat", "desc": "좌석 iframe"},
            {"name": "seat_map", "xpath": '//*[@id="seatMap"]', "category": "seat", "desc": "좌석맵"},
        ]
    },
    "빈 템플릿": {
        "name": "새 사이트",
        "url": "",
        "login_url": "",
        "description": "사용자 정의 사이트",
        "items": []
    }
}


# ============================================================================
# 데이터 클래스
# ============================================================================

@dataclass
class XPathItem:
    """XPath 항목"""
    name: str
    xpath: str
    category: str
    description: str = ""
    css_selector: str = ""
    is_verified: bool = False
    element_tag: str = ""
    element_text: str = ""
    found_window: str = ""
    found_frame: str = ""
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class SiteConfig:
    """사이트 설정"""
    name: str
    url: str
    login_url: str = ""
    description: str = ""
    items: List[XPathItem] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'url': self.url,
            'login_url': self.login_url,
            'description': self.description,
            'items': [item.to_dict() for item in self.items],
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'SiteConfig':
        items = [XPathItem(**item) for item in data.get('items', [])]
        return cls(
            name=data.get('name', ''),
            url=data.get('url', ''),
            login_url=data.get('login_url', ''),
            description=data.get('description', ''),
            items=items,
            created_at=data.get('created_at', ''),
            updated_at=data.get('updated_at', '')
        )
    
    @classmethod
    def from_preset(cls, preset_name: str) -> 'SiteConfig':
        preset = SITE_PRESETS.get(preset_name, SITE_PRESETS["빈 템플릿"])
        items = [
            XPathItem(
                name=item["name"],
                xpath=item["xpath"],
                category=item["category"],
                description=item.get("desc", "")
            )
            for item in preset.get("items", [])
        ]
        return cls(
            name=preset["name"],
            url=preset["url"],
            login_url=preset.get("login_url", ""),
            description=preset.get("description", ""),
            items=items
        )
    
    def get_item(self, name: str) -> Optional[XPathItem]:
        for item in self.items:
            if item.name == name:
                return item
        return None
    
    def add_or_update(self, item: XPathItem):
        existing = self.get_item(item.name)
        if existing:
            idx = self.items.index(existing)
            self.items[idx] = item
        else:
            self.items.append(item)
        self.updated_at = datetime.now().isoformat()
    
    def remove_item(self, name: str):
        self.items = [item for item in self.items if item.name != name]
        self.updated_at = datetime.now().isoformat()
    
    def get_categories(self) -> List[str]:
        return list(set(item.category for item in self.items))


# ============================================================================
# 스타일
# ============================================================================

STYLE = """
* {
    font-family: 'Malgun Gothic', 'Segoe UI', sans-serif;
}

QMainWindow {
    background-color: #0d1b2a;
}

QWidget {
    background-color: #0d1b2a;
    color: #e0e1dd;
}

/* 그룹박스 */
QGroupBox {
    border: 2px solid #1b263b;
    border-radius: 10px;
    margin-top: 15px;
    padding: 15px;
    font-weight: bold;
    font-size: 11pt;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 20px;
    padding: 0 10px;
    color: #00d4ff;
}

/* 입력 필드 */
QLineEdit, QPlainTextEdit, QTextEdit {
    background-color: #1b263b;
    border: 2px solid #415a77;
    border-radius: 8px;
    padding: 10px;
    color: #e0e1dd;
    font-size: 10pt;
    selection-background-color: #00d4ff;
}

QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {
    border-color: #00d4ff;
}

QLineEdit:disabled {
    background-color: #0d1b2a;
    color: #778da9;
}

/* 콤보박스 */
QComboBox {
    background-color: #1b263b;
    border: 2px solid #415a77;
    border-radius: 8px;
    padding: 8px 15px;
    color: #e0e1dd;
    min-width: 120px;
}

QComboBox:hover {
    border-color: #00d4ff;
}

QComboBox::drop-down {
    border: none;
    width: 30px;
}

QComboBox QAbstractItemView {
    background-color: #1b263b;
    border: 2px solid #415a77;
    selection-background-color: #00d4ff;
    selection-color: #0d1b2a;
}

/* 버튼 기본 */
QPushButton {
    background-color: #415a77;
    border: none;
    border-radius: 8px;
    padding: 12px 24px;
    color: white;
    font-weight: bold;
    font-size: 10pt;
}

QPushButton:hover {
    background-color: #778da9;
}

QPushButton:pressed {
    background-color: #1b263b;
}

QPushButton:disabled {
    background-color: #1b263b;
    color: #415a77;
}

/* 버튼 스타일 */
QPushButton#primary {
    background-color: #00d4ff;
    color: #0d1b2a;
}

QPushButton#primary:hover {
    background-color: #33ddff;
}

QPushButton#success {
    background-color: #06d6a0;
    color: #0d1b2a;
}

QPushButton#success:hover {
    background-color: #2ee8b7;
}

QPushButton#danger {
    background-color: #ef476f;
}

QPushButton#danger:hover {
    background-color: #f26d8a;
}

QPushButton#warning {
    background-color: #ffd166;
    color: #0d1b2a;
}

QPushButton#picker {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #9b59b6, stop:1 #8e44ad);
    font-size: 14pt;
    padding: 18px 30px;
    border-radius: 12px;
}

QPushButton#picker:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #a66bbe, stop:1 #9b59b6);
}

QPushButton#picker:disabled {
    background: #1b263b;
}

/* 테이블 */
QTableWidget {
    background-color: #1b263b;
    border: 2px solid #415a77;
    border-radius: 10px;
    gridline-color: #415a77;
}

QTableWidget::item {
    padding: 10px;
    border-bottom: 1px solid #415a77;
}

QTableWidget::item:selected {
    background-color: #00d4ff;
    color: #0d1b2a;
}

QHeaderView::section {
    background-color: #0d1b2a;
    color: #00d4ff;
    padding: 12px;
    border: none;
    border-bottom: 2px solid #415a77;
    font-weight: bold;
}

/* 탭 */
QTabWidget::pane {
    border: 2px solid #415a77;
    border-radius: 10px;
    background-color: #1b263b;
    margin-top: -2px;
}

QTabBar::tab {
    background-color: #0d1b2a;
    color: #778da9;
    padding: 12px 25px;
    margin-right: 3px;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    font-weight: bold;
}

QTabBar::tab:selected {
    background-color: #1b263b;
    color: #00d4ff;
}

QTabBar::tab:hover:!selected {
    background-color: #1b263b;
    color: #e0e1dd;
}

/* 프로그레스바 */
QProgressBar {
    border: 2px solid #415a77;
    border-radius: 8px;
    background-color: #1b263b;
    text-align: center;
    color: white;
    font-weight: bold;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #00d4ff, stop:1 #06d6a0);
    border-radius: 6px;
}

/* 스크롤바 */
QScrollBar:vertical {
    background-color: #0d1b2a;
    width: 14px;
    border-radius: 7px;
}

QScrollBar::handle:vertical {
    background-color: #415a77;
    border-radius: 7px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background-color: #778da9;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* 리스트/트리 */
QListWidget, QTreeWidget {
    background-color: #1b263b;
    border: 2px solid #415a77;
    border-radius: 10px;
    padding: 5px;
}

QListWidget::item, QTreeWidget::item {
    padding: 8px;
    border-radius: 5px;
}

QListWidget::item:selected, QTreeWidget::item:selected {
    background-color: #00d4ff;
    color: #0d1b2a;
}

QListWidget::item:hover:!selected, QTreeWidget::item:hover:!selected {
    background-color: #415a77;
}

/* 툴바 */
QToolBar {
    background-color: #0d1b2a;
    border: none;
    spacing: 8px;
    padding: 8px;
}

/* 메뉴 */
QMenuBar {
    background-color: #0d1b2a;
    color: #e0e1dd;
    padding: 5px;
}

QMenuBar::item:selected {
    background-color: #1b263b;
}

QMenu {
    background-color: #1b263b;
    border: 2px solid #415a77;
    border-radius: 8px;
    padding: 5px;
}

QMenu::item {
    padding: 10px 30px;
    border-radius: 5px;
}

QMenu::item:selected {
    background-color: #00d4ff;
    color: #0d1b2a;
}

/* 상태바 */
QStatusBar {
    background-color: #0d1b2a;
    color: #778da9;
    border-top: 1px solid #415a77;
}

/* 스플리터 */
QSplitter::handle {
    background-color: #415a77;
    width: 3px;
    margin: 0 5px;
}

QSplitter::handle:hover {
    background-color: #00d4ff;
}

/* 체크박스 */
QCheckBox {
    spacing: 10px;
}

QCheckBox::indicator {
    width: 22px;
    height: 22px;
    border-radius: 5px;
    border: 2px solid #415a77;
    background-color: #1b263b;
}

QCheckBox::indicator:checked {
    background-color: #00d4ff;
    border-color: #00d4ff;
}

/* 라벨 */
QLabel#title {
    font-size: 16pt;
    font-weight: bold;
    color: #00d4ff;
}

QLabel#subtitle {
    font-size: 11pt;
    color: #778da9;
}

QLabel#status_connected {
    color: #06d6a0;
    font-weight: bold;
}

QLabel#status_disconnected {
    color: #ef476f;
    font-weight: bold;
}
"""


# ============================================================================
# 브라우저 매니저
# ============================================================================

class BrowserManager:
    """브라우저 관리"""
    
    PICKER_SCRIPT = '''
    (function() {
        // 이미 활성화되어 있으면 무시
        if (window.__pickerActive) return "ALREADY_ACTIVE";
        
        window.__pickerActive = true;
        window.__pickerResult = null;
        window.__pickerLocked = false;  // 선택 고정 상태
        window.__lockedData = null;     // 고정된 요소 정보
        
        // 스타일 추가
        var style = document.createElement('style');
        style.id = '__pickerStyle';
        style.textContent = `
            .__picker_highlight {
                outline: 3px solid #ff3366 !important;
                outline-offset: 2px !important;
                background-color: rgba(255, 51, 102, 0.15) !important;
                cursor: crosshair !important;
            }
            .__picker_locked {
                outline: 4px solid #00ff88 !important;
                outline-offset: 2px !important;
                background-color: rgba(0, 255, 136, 0.25) !important;
            }
            .__picker_tooltip {
                position: fixed;
                top: 15px;
                left: 50%;
                transform: translateX(-50%);
                background: linear-gradient(135deg, #1a1a2e, #16213e);
                color: #00ff88;
                padding: 15px 25px;
                border-radius: 12px;
                font-family: 'Consolas', monospace;
                font-size: 13px;
                z-index: 2147483647;
                border: 2px solid #00ff88;
                box-shadow: 0 10px 40px rgba(0,255,136,0.3);
                max-width: 90%;
                word-break: break-all;
                line-height: 1.6;
                user-select: text !important;
            }
            .__picker_tooltip.locked {
                border-color: #ffd166;
                background: linear-gradient(135deg, #2d2d0a, #3d3d0a);
            }
            .__picker_info {
                position: fixed;
                bottom: 20px;
                left: 50%;
                transform: translateX(-50%);
                background: linear-gradient(135deg, #9b59b6, #8e44ad);
                color: white;
                padding: 15px 30px;
                border-radius: 30px;
                font-size: 14px;
                font-weight: bold;
                z-index: 2147483647;
                box-shadow: 0 5px 25px rgba(155,89,182,0.5);
            }
            .__picker_info.locked {
                background: linear-gradient(135deg, #27ae60, #2ecc71);
            }
            .__picker_btn {
                display: inline-block;
                margin: 5px 5px 0 0;
                padding: 8px 16px;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                font-size: 12px;
                font-weight: bold;
            }
            .__picker_btn_copy {
                background: #00ff88;
                color: #1a1a2e;
            }
            .__picker_btn_copy:hover {
                background: #33ffaa;
            }
            .__picker_btn_confirm {
                background: #3498db;
                color: white;
            }
            .__picker_btn_confirm:hover {
                background: #5dade2;
            }
            .__picker_btn_cancel {
                background: #e74c3c;
                color: white;
            }
            .__picker_btn_cancel:hover {
                background: #ec7063;
            }
            .__picker_xpath_box {
                background: #0d0d1a;
                border: 1px solid #00ff88;
                border-radius: 6px;
                padding: 10px;
                margin-top: 10px;
                font-family: 'Consolas', monospace;
                font-size: 12px;
                color: #ffd166;
                word-break: break-all;
                user-select: all !important;
                cursor: text;
            }
        `;
        document.head.appendChild(style);
        
        // 툴팁
        var tooltip = document.createElement('div');
        tooltip.className = '__picker_tooltip';
        tooltip.innerHTML = '🎯 요소 위에 마우스를 올리세요...';
        document.body.appendChild(tooltip);
        
        // 안내
        var info = document.createElement('div');
        info.className = '__picker_info';
        info.innerHTML = '🎯 Space: 호버고정 | 클릭: 선택고정 | 더블클릭: 복사+확정 | Ctrl+C: 복사 | ESC: 취소';
        document.body.appendChild(info);
        
        var lastEl = null;
        var lockedEl = null;
        
        // XPath 생성
        function getXPath(el) {
            if (!el) return '';
            if (el.id) return '//*[@id="' + el.id + '"]';
            if (el === document.body) return '/html/body';
            if (el === document.documentElement) return '/html';
            
            var parent = el.parentNode;
            if (!parent) return '';
            
            var siblings = parent.children;
            var sameTag = [];
            for (var i = 0; i < siblings.length; i++) {
                if (siblings[i].tagName === el.tagName) sameTag.push(siblings[i]);
            }
            
            var tag = el.tagName.toLowerCase();
            var index = sameTag.indexOf(el) + 1;
            var path = sameTag.length > 1 ? tag + '[' + index + ']' : tag;
            
            return getXPath(parent) + '/' + path;
        }
        
        // CSS 선택자
        function getCSS(el) {
            if (!el) return '';
            if (el.id) return '#' + el.id;
            
            var path = [];
            while (el && el.nodeType === 1) {
                var sel = el.tagName.toLowerCase();
                if (el.id) {
                    path.unshift('#' + el.id);
                    break;
                }
                if (el.className && typeof el.className === 'string') {
                    var cls = el.className.trim().split(/\\s+/).filter(c => c && !c.startsWith('__picker')).slice(0,2);
                    if (cls.length) sel += '.' + cls.join('.');
                }
                path.unshift(sel);
                el = el.parentNode;
            }
            return path.slice(-4).join(' > ');
        }
        
        // 클립보드 복사
        function copyToClipboard(text) {
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(text).then(function() {
                    showCopyFeedback('✅ 복사됨!');
                }).catch(function() {
                    fallbackCopy(text);
                });
            } else {
                fallbackCopy(text);
            }
        }
        
        function fallbackCopy(text) {
            var ta = document.createElement('textarea');
            ta.value = text;
            ta.style.position = 'fixed';
            ta.style.left = '-9999px';
            document.body.appendChild(ta);
            ta.select();
            try {
                document.execCommand('copy');
                showCopyFeedback('✅ 복사됨!');
            } catch(e) {
                showCopyFeedback('❌ 복사 실패');
            }
            document.body.removeChild(ta);
        }
        
        function showCopyFeedback(msg) {
            var fb = document.createElement('div');
            fb.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:#00ff88;color:#1a1a2e;padding:15px 30px;border-radius:10px;font-size:16px;font-weight:bold;z-index:2147483647;';
            fb.textContent = msg;
            document.body.appendChild(fb);
            setTimeout(function() { fb.remove(); }, 1000);
        }
        
        // 마우스오버
        function onOver(e) {
            if (window.__pickerLocked) return;  // 고정 상태면 무시
            
            if (lastEl) lastEl.classList.remove('__picker_highlight');
            
            var t = e.target;
            if (t.className && typeof t.className === 'string' && t.className.includes('__picker')) return;
            
            t.classList.add('__picker_highlight');
            lastEl = t;
            
            var xpath = getXPath(t);
            var text = (t.textContent || '').trim().substring(0, 40);
            var id = t.id ? ' #' + t.id : '';
            
            tooltip.innerHTML = 
                '<b>XPath:</b> ' + xpath.substring(0, 80) + (xpath.length > 80 ? '...' : '') +
                '<br><b>Tag:</b> &lt;' + t.tagName.toLowerCase() + '&gt;' + id +
                (text ? '<br><b>Text:</b> ' + text + (text.length >= 40 ? '...' : '') : '');
        }
        
        // 고정 모드 UI 표시
        function showLockedUI(data) {
            tooltip.className = '__picker_tooltip locked';
            tooltip.innerHTML = 
                '<div style="color:#ffd166;font-size:14px;margin-bottom:10px;">🔒 <b>선택 고정됨!</b> 아래 XPath를 복사하세요</div>' +
                '<div class="__picker_xpath_box" id="__xpathBox">' + data.xpath + '</div>' +
                '<div style="margin-top:10px;">' +
                '<button class="__picker_btn __picker_btn_copy" id="__copyXpath">📋 XPath 복사</button>' +
                '<button class="__picker_btn __picker_btn_copy" id="__copyCss">📋 CSS 복사</button>' +
                '<button class="__picker_btn __picker_btn_confirm" id="__confirmPick">✓ 확인 (프로그램으로 전송)</button>' +
                '<button class="__picker_btn __picker_btn_cancel" id="__cancelPick">✕ 취소</button>' +
                '</div>' +
                '<div style="margin-top:8px;color:#778da9;font-size:11px;">ID: ' + (data.id || '-') + ' | Tag: &lt;' + data.tag + '&gt;</div>';
            
            info.className = '__picker_info locked';
            info.innerHTML = '🔒 고정됨 | Ctrl+C: 복사 | Enter: 확정 | ESC: 취소';
            
            // 버튼 이벤트
            setTimeout(function() {
                var copyBtn = document.getElementById('__copyXpath');
                var copyCssBtn = document.getElementById('__copyCss');
                var confirmBtn = document.getElementById('__confirmPick');
                var cancelBtn = document.getElementById('__cancelPick');
                
                if (copyBtn) copyBtn.onclick = function(e) { e.stopPropagation(); copyToClipboard(data.xpath); };
                if (copyCssBtn) copyCssBtn.onclick = function(e) { e.stopPropagation(); copyToClipboard(data.css); };
                if (confirmBtn) confirmBtn.onclick = function(e) { e.stopPropagation(); confirmSelection(); };
                if (cancelBtn) cancelBtn.onclick = function(e) { e.stopPropagation(); unlockSelection(); };
            }, 50);
        }
        
        // 선택 고정
        function lockSelection(t) {
            window.__pickerLocked = true;
            lockedEl = t;
            
            if (lastEl) lastEl.classList.remove('__picker_highlight');
            t.classList.add('__picker_locked');
            
            var data = {
                xpath: getXPath(t),
                css: getCSS(t),
                tag: t.tagName.toLowerCase(),
                id: t.id || '',
                className: (typeof t.className === 'string' ? t.className : '').replace(/__picker[^\\s]*/g, '').trim(),
                text: (t.textContent || '').trim().substring(0, 150),
                name: t.getAttribute('name') || '',
                href: t.getAttribute('href') || '',
                value: t.value || '',
                html: t.outerHTML.substring(0, 400)
            };
            window.__lockedData = data;
            
            showLockedUI(data);
        }
        
        // 선택 해제 (다시 선택 모드)
        function unlockSelection() {
            window.__pickerLocked = false;
            window.__lockedData = null;
            
            if (lockedEl) {
                lockedEl.classList.remove('__picker_locked');
                lockedEl = null;
            }
            
            tooltip.className = '__picker_tooltip';
            tooltip.innerHTML = '🎯 요소 위에 마우스를 올리세요...';
            
            info.className = '__picker_info';
            info.innerHTML = '🎯 클릭: 선택 고정 | ESC: 취소';
        }
        
        // 선택 확정 (프로그램으로 전송)
        function confirmSelection() {
            if (window.__lockedData) {
                window.__pickerResult = window.__lockedData;
            }
            cleanup();
        }
        
        // 클릭
        function onClick(e) {
            var t = e.target;
            
            // picker UI 요소는 무시 (단, 복사 등의 버튼은 별도 처리됨)
            if (t.className && typeof t.className === 'string' && t.className.includes('__picker')) {
                return;
            }
            
            e.preventDefault();
            e.stopPropagation();
            e.stopImmediatePropagation();
            
            if (window.__pickerLocked) {
                // 이미 고정된 상태에서 다른 곳 클릭 -> 해제하고 새로 선택
                unlockSelection();
                lockSelection(t);
            } else {
                // 처음 클릭 -> 고정
                lockSelection(t);
            }
            
            return false;
        }
        
        // 더블클릭 = 자동 복사 + 프로그램으로 전송
        function onDblClick(e) {
            var t = e.target;
            
            if (t.className && typeof t.className === 'string' && t.className.includes('__picker')) {
                return;
            }
            
            e.preventDefault();
            e.stopPropagation();
            e.stopImmediatePropagation();
            
            // 요소 선택하고 XPath 복사
            var xpath = getXPath(t);
            copyToClipboard(xpath);
            
            // 결과 설정하고 종료
            window.__pickerResult = {
                xpath: xpath,
                css: getCSS(t),
                tag: t.tagName.toLowerCase(),
                id: t.id || '',
                className: (typeof t.className === 'string' ? t.className : '').replace(/__picker[^\\s]*/g, '').trim(),
                text: (t.textContent || '').trim().substring(0, 150),
                name: t.getAttribute('name') || '',
                href: t.getAttribute('href') || '',
                value: t.value || '',
                html: t.outerHTML.substring(0, 400)
            };
            
            setTimeout(function() {
                cleanup();
            }, 500);  // 복사 피드백 보여준 후 종료
            
            return false;
        }
        
        // ESC, Space, Enter, Ctrl+C 키 처리
        function onKey(e) {
            if (e.key === 'Escape') {
                if (window.__pickerLocked) {
                    unlockSelection();
                } else {
                    window.__pickerResult = { cancelled: true };
                    cleanup();
                }
            } else if (e.key === ' ' || e.code === 'Space') {
                // Space: 현재 호버된 요소를 즉시 고정 (해제 가능)
                e.preventDefault();
                if (window.__pickerLocked) {
                    // 이미 고정된 상태면 해제
                    unlockSelection();
                    showCopyFeedback('🔓 고정 해제');
                } else if (lastEl) {
                    // 현재 호버된 요소를 고정
                    lockSelection(lastEl);
                    showCopyFeedback('❄️ 호버 고정!');
                }
            } else if (e.key === 'Enter' && window.__pickerLocked) {
                confirmSelection();
            } else if ((e.ctrlKey || e.metaKey) && e.key === 'c') {
                // Ctrl+C: 현재 요소 XPath 복사
                if (window.__pickerLocked && window.__lockedData) {
                    e.preventDefault();
                    copyToClipboard(window.__lockedData.xpath);
                } else if (lastEl) {
                    e.preventDefault();
                    copyToClipboard(getXPath(lastEl));
                }
            }
        }
        
        // 정리
        function cleanup() {
            window.__pickerActive = false;
            window.__pickerLocked = false;
            window.__lockedData = null;
            
            document.removeEventListener('mouseover', onOver, true);
            document.removeEventListener('click', onClick, true);
            document.removeEventListener('dblclick', onDblClick, true);
            document.removeEventListener('keydown', onKey, true);
            
            if (lastEl) lastEl.classList.remove('__picker_highlight');
            if (lockedEl) lockedEl.classList.remove('__picker_locked');
            
            var s = document.getElementById('__pickerStyle');
            if (s) s.remove();
            if (tooltip.parentNode) tooltip.remove();
            if (info.parentNode) info.remove();
        }
        
        document.addEventListener('mouseover', onOver, true);
        document.addEventListener('click', onClick, true);
        document.addEventListener('dblclick', onDblClick, true);
        document.addEventListener('keydown', onKey, true);
        
        return "OK";
    })();
    '''
    
    # 오버레이 모드 - 실제 요소와 상호작용하지 않음
    PICKER_SCRIPT_OVERLAY = '''
    (function() {
        if (window.__pickerActive) return "ALREADY_ACTIVE";
        
        window.__pickerActive = true;
        window.__pickerResult = null;
        
        // 전체 화면 오버레이 생성
        var overlay = document.createElement('div');
        overlay.id = '__pickerOverlay';
        overlay.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;z-index:2147483646;cursor:crosshair;';
        document.body.appendChild(overlay);
        
        // 하이라이트 박스 (요소 위에 표시)
        var highlightBox = document.createElement('div');
        highlightBox.id = '__pickerHighlight';
        highlightBox.style.cssText = 'position:fixed;pointer-events:none;border:3px solid #ff3366;background:rgba(255,51,102,0.15);z-index:2147483647;display:none;';
        document.body.appendChild(highlightBox);
        
        // 스타일
        var style = document.createElement('style');
        style.id = '__pickerStyle';
        style.textContent = `
            .__picker_tooltip {
                position: fixed;
                top: 15px;
                left: 50%;
                transform: translateX(-50%);
                background: linear-gradient(135deg, #1a1a2e, #16213e);
                color: #00ff88;
                padding: 15px 25px;
                border-radius: 12px;
                font-family: 'Consolas', monospace;
                font-size: 13px;
                z-index: 2147483647;
                border: 2px solid #00ff88;
                box-shadow: 0 10px 40px rgba(0,255,136,0.3);
                max-width: 90%;
                word-break: break-all;
                pointer-events: auto;
                user-select: text;
            }
            .__picker_info {
                position: fixed;
                bottom: 20px;
                left: 50%;
                transform: translateX(-50%);
                background: linear-gradient(135deg, #e74c3c, #c0392b);
                color: white;
                padding: 15px 30px;
                border-radius: 30px;
                font-size: 14px;
                font-weight: bold;
                z-index: 2147483647;
                box-shadow: 0 5px 25px rgba(231,76,60,0.5);
                pointer-events: auto;
            }
            .__picker_btn {
                display: inline-block;
                margin: 5px 5px 0 0;
                padding: 8px 16px;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                font-size: 12px;
                font-weight: bold;
                pointer-events: auto;
            }
            .__picker_btn_copy { background: #00ff88; color: #1a1a2e; }
            .__picker_btn_confirm { background: #3498db; color: white; }
            .__picker_btn_cancel { background: #e74c3c; color: white; }
        `;
        document.head.appendChild(style);
        
        // 툴팁
        var tooltip = document.createElement('div');
        tooltip.className = '__picker_tooltip';
        tooltip.innerHTML = '🛡️ <b>오버레이 모드</b> - 마우스를 올려 요소 확인';
        document.body.appendChild(tooltip);
        
        // 안내
        var info = document.createElement('div');
        info.className = '__picker_info';
        info.innerHTML = '🛡️ 오버레이 ON | Space: 호버고정 | 클릭: 선택 | 더블클릭: 복사+확정 | ESC: 취소';
        document.body.appendChild(info);
        
        var lastEl = null;
        var lockedEl = null;
        var isLocked = false;
        var lockedData = null;
        
        function getXPath(el) {
            if (!el) return '';
            if (el.id) return '//*[@id="' + el.id + '"]';
            if (el === document.body) return '/html/body';
            if (el === document.documentElement) return '/html';
            var parent = el.parentNode;
            if (!parent) return '';
            var siblings = parent.children;
            var sameTag = [];
            for (var i = 0; i < siblings.length; i++) {
                if (siblings[i].tagName === el.tagName) sameTag.push(siblings[i]);
            }
            var tag = el.tagName.toLowerCase();
            var index = sameTag.indexOf(el) + 1;
            var path = sameTag.length > 1 ? tag + '[' + index + ']' : tag;
            return getXPath(parent) + '/' + path;
        }
        
        function getCSS(el) {
            if (!el) return '';
            if (el.id) return '#' + el.id;
            var path = [];
            while (el && el.nodeType === 1) {
                var sel = el.tagName.toLowerCase();
                if (el.id) { path.unshift('#' + el.id); break; }
                if (el.className && typeof el.className === 'string') {
                    var cls = el.className.trim().split(/\\s+/).filter(c => c && !c.startsWith('__picker')).slice(0,2);
                    if (cls.length) sel += '.' + cls.join('.');
                }
                path.unshift(sel);
                el = el.parentNode;
            }
            return path.slice(-4).join(' > ');
        }
        
        function copyToClipboard(text) {
            if (navigator.clipboard) {
                navigator.clipboard.writeText(text).then(function() {
                    showFeedback('✅ 복사됨!');
                }).catch(function() { fallbackCopy(text); });
            } else { fallbackCopy(text); }
        }
        
        function fallbackCopy(text) {
            var ta = document.createElement('textarea');
            ta.value = text;
            ta.style.cssText = 'position:fixed;left:-9999px;';
            document.body.appendChild(ta);
            ta.select();
            try { document.execCommand('copy'); showFeedback('✅ 복사됨!'); } 
            catch(e) { showFeedback('❌ 실패'); }
            document.body.removeChild(ta);
        }
        
        function showFeedback(msg) {
            var fb = document.createElement('div');
            fb.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:#00ff88;color:#1a1a2e;padding:15px 30px;border-radius:10px;font-size:16px;font-weight:bold;z-index:2147483647;pointer-events:none;';
            fb.textContent = msg;
            document.body.appendChild(fb);
            setTimeout(function() { fb.remove(); }, 800);
        }
        
        function getElementFromPoint(x, y) {
            overlay.style.display = 'none';
            highlightBox.style.display = 'none';
            var el = document.elementFromPoint(x, y);
            overlay.style.display = 'block';
            // picker UI 제외
            while (el && el.id && el.id.startsWith('__picker')) {
                el = el.parentElement;
            }
            return el;
        }
        
        function highlightElement(el) {
            if (!el || el === document.body || el === document.documentElement) {
                highlightBox.style.display = 'none';
                return;
            }
            var rect = el.getBoundingClientRect();
            highlightBox.style.left = rect.left + 'px';
            highlightBox.style.top = rect.top + 'px';
            highlightBox.style.width = rect.width + 'px';
            highlightBox.style.height = rect.height + 'px';
            highlightBox.style.display = 'block';
            
            if (isLocked) {
                highlightBox.style.borderColor = '#00ff88';
                highlightBox.style.background = 'rgba(0,255,136,0.2)';
            } else {
                highlightBox.style.borderColor = '#ff3366';
                highlightBox.style.background = 'rgba(255,51,102,0.15)';
            }
        }
        
        function updateTooltip(el) {
            if (!el) return;
            var xpath = getXPath(el);
            var text = (el.textContent || '').trim().substring(0, 40);
            var id = el.id ? ' #' + el.id : '';
            
            if (isLocked) {
                tooltip.innerHTML = 
                    '<div style="color:#ffd166;margin-bottom:8px;">🔒 <b>선택됨</b></div>' +
                    '<div style="background:#0d0d1a;padding:8px;border-radius:4px;color:#ffd166;margin-bottom:8px;">' + xpath + '</div>' +
                    '<button class="__picker_btn __picker_btn_copy" id="__copyBtn">📋 복사</button>' +
                    '<button class="__picker_btn __picker_btn_confirm" id="__confirmBtn">✓ 확정</button>' +
                    '<button class="__picker_btn __picker_btn_cancel" id="__cancelBtn">✕ 해제</button>';
                
                setTimeout(function() {
                    var copyBtn = document.getElementById('__copyBtn');
                    var confirmBtn = document.getElementById('__confirmBtn');
                    var cancelBtn = document.getElementById('__cancelBtn');
                    if (copyBtn) copyBtn.onclick = function(e) { e.stopPropagation(); copyToClipboard(lockedData.xpath); };
                    if (confirmBtn) confirmBtn.onclick = function(e) { e.stopPropagation(); confirm(); };
                    if (cancelBtn) cancelBtn.onclick = function(e) { e.stopPropagation(); unlock(); };
                }, 30);
            } else {
                tooltip.innerHTML = 
                    '<b>XPath:</b> ' + xpath.substring(0, 80) + (xpath.length > 80 ? '...' : '') +
                    '<br><b>Tag:</b> &lt;' + el.tagName.toLowerCase() + '&gt;' + id +
                    (text ? '<br><b>Text:</b> ' + text : '');
            }
        }
        
        function lock(el) {
            isLocked = true;
            lockedEl = el;
            lockedData = {
                xpath: getXPath(el),
                css: getCSS(el),
                tag: el.tagName.toLowerCase(),
                id: el.id || '',
                className: (typeof el.className === 'string' ? el.className : '').trim(),
                text: (el.textContent || '').trim().substring(0, 150),
                name: el.getAttribute('name') || '',
                href: el.getAttribute('href') || '',
                value: el.value || '',
                html: el.outerHTML.substring(0, 400)
            };
            highlightElement(el);
            updateTooltip(el);
            info.innerHTML = '🔒 고정됨 | Ctrl+C: 복사 | Enter: 확정 | ESC: 해제';
            info.style.background = 'linear-gradient(135deg, #27ae60, #2ecc71)';
        }
        
        function unlock() {
            isLocked = false;
            lockedEl = null;
            lockedData = null;
            info.innerHTML = '🛡️ 오버레이 ON | 클릭: 선택 | 더블클릭: 복사+확정 | ESC: 취소';
            info.style.background = 'linear-gradient(135deg, #e74c3c, #c0392b)';
            tooltip.innerHTML = '🛡️ <b>오버레이 모드</b> - 마우스를 올려 요소 확인';
        }
        
        function confirm() {
            if (lockedData) {
                window.__pickerResult = lockedData;
            }
            cleanup();
        }
        
        function onMouseMove(e) {
            if (isLocked) return;
            var el = getElementFromPoint(e.clientX, e.clientY);
            if (el && el !== lastEl) {
                lastEl = el;
                highlightElement(el);
                updateTooltip(el);
            }
        }
        
        function onClick(e) {
            if (e.target.className && e.target.className.includes && e.target.className.includes('__picker_btn')) return;
            
            e.preventDefault();
            e.stopPropagation();
            
            var el = getElementFromPoint(e.clientX, e.clientY);
            if (el) {
                if (isLocked) {
                    unlock();
                }
                lock(el);
            }
        }
        
        function onDblClick(e) {
            e.preventDefault();
            e.stopPropagation();
            
            var el = getElementFromPoint(e.clientX, e.clientY);
            if (el) {
                var xpath = getXPath(el);
                copyToClipboard(xpath);
                
                window.__pickerResult = {
                    xpath: xpath,
                    css: getCSS(el),
                    tag: el.tagName.toLowerCase(),
                    id: el.id || '',
                    className: (typeof el.className === 'string' ? el.className : '').trim(),
                    text: (el.textContent || '').trim().substring(0, 150),
                    name: el.getAttribute('name') || '',
                    href: el.getAttribute('href') || '',
                    value: el.value || '',
                    html: el.outerHTML.substring(0, 400)
                };
                
                setTimeout(cleanup, 500);
            }
        }
        
        function onKeyDown(e) {
            if (e.key === 'Escape') {
                if (isLocked) { unlock(); }
                else { window.__pickerResult = { cancelled: true }; cleanup(); }
            } else if (e.key === ' ' || e.code === 'Space') {
                // Space: 현재 호버된 요소를 즉시 고정/해제
                e.preventDefault();
                if (isLocked) {
                    unlock();
                    showFeedback('🔓 해제');
                } else if (lastEl) {
                    lock(lastEl);
                    showFeedback('❄️ 호버 고정!');
                }
            } else if (e.key === 'Enter' && isLocked) {
                confirm();
            } else if ((e.ctrlKey || e.metaKey) && e.key === 'c') {
                e.preventDefault();
                if (isLocked && lockedData) {
                    copyToClipboard(lockedData.xpath);
                } else if (lastEl) {
                    copyToClipboard(getXPath(lastEl));
                }
            }
        }
        
        function cleanup() {
            window.__pickerActive = false;
            
            overlay.removeEventListener('mousemove', onMouseMove);
            overlay.removeEventListener('click', onClick);
            overlay.removeEventListener('dblclick', onDblClick);
            document.removeEventListener('keydown', onKeyDown, true);
            
            overlay.remove();
            highlightBox.remove();
            tooltip.remove();
            info.remove();
            var s = document.getElementById('__pickerStyle');
            if (s) s.remove();
        }
        
        overlay.addEventListener('mousemove', onMouseMove);
        overlay.addEventListener('click', onClick);
        overlay.addEventListener('dblclick', onDblClick);
        document.addEventListener('keydown', onKeyDown, true);
        
        return "OK";
    })();
    '''
    
    def __init__(self):
        self.driver = None
        self.current_frame_path = ""  # 현재 활성 프레임 경로
        self.frame_cache = []  # 캐시된 프레임 목록
        
        # 연결 상태 관리
        self._last_alive_check = 0  # 마지막 연결 체크 시간
        self._alive_cache = False  # 연결 상태 캐시
        self._alive_cache_duration = 0.5  # 캐시 유효 시간 (초)
        self._reconnect_attempts = 0  # 재연결 시도 횟수
        self._max_reconnect_attempts = 3  # 최대 재연결 시도
    
    def create_driver(self, use_undetected: bool = True) -> bool:
        """드라이버 생성"""
        try:
            logger.info("브라우저 드라이버 생성 시작...")
            if use_undetected and UC_AVAILABLE:
                options = uc.ChromeOptions()
                options.add_argument('--start-maximized')
                options.add_argument('--disable-popup-blocking')
                options.add_argument('--lang=ko-KR')
                self.driver = uc.Chrome(options=options, use_subprocess=True)
                logger.info("Undetected Chrome 드라이버 생성 완료")
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
                logger.info("표준 Chrome 드라이버 생성 완료")
            
            return True
        except Exception as e:
            logger.error(f"드라이버 생성 실패: {e}")
            return False
    
    def close(self):
        """브라우저 닫기"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("브라우저 종료")
            except Exception as e:
                logger.warning(f"브라우저 종료 중 오류: {e}")
            self.driver = None
    
    def is_alive(self) -> bool:
        """연결 상태 확인 - 캐싱 및 자동 복구 지원"""
        if not self.driver:
            self._alive_cache = False
            return False
        
        # 캐시된 결과 사용 (짧은 시간 내 중복 호출 방지)
        current_time = time.time()
        if (current_time - self._last_alive_check) < self._alive_cache_duration:
            return self._alive_cache
        
        self._last_alive_check = current_time
        
        try:
            # 현재 윈도우 핸들 확인 (기본 체크)
            _ = self.driver.current_window_handle
            # 추가 체크: 페이지 제목 접근 (실제 연결 상태 확인)
            _ = self.driver.title
            self._alive_cache = True
            self._reconnect_attempts = 0  # 성공시 재연결 시도 초기화
            return True
        except NoSuchWindowException:
            # 현재 윈도우가 닫힘 - 다른 윈도우로 자동 전환 시도
            logger.warning("현재 윈도우가 닫힘, 다른 윈도우로 전환 시도...")
            result = self._recover_to_available_window()
            self._alive_cache = result
            return result
        except WebDriverException as e:
            error_msg = str(e).lower()
            # 브라우저 자체가 종료됨 (연결 불가)
            if any(keyword in error_msg for keyword in ['disconnected', 'not reachable', 'session deleted', 'invalid session']):
                logger.error(f"브라우저 연결 끊김: {e}")
                self._alive_cache = False
                self.driver = None
                return False
            # 다른 WebDriver 오류는 복구 시도
            logger.warning(f"WebDriver 오류, 복구 시도: {e}")
            result = self._recover_to_available_window()
            self._alive_cache = result
            return result
        except Exception as e:
            logger.error(f"연결 확인 오류: {e}")
            result = self._recover_to_available_window()
            self._alive_cache = result
            return result
    
    def _recover_to_available_window(self) -> bool:
        """사용 가능한 다른 윈도우로 자동 복구 - 재시도 로직 포함"""
        if not self.driver:
            return False
        
        # 재연결 시도 횟수 제한
        if self._reconnect_attempts >= self._max_reconnect_attempts:
            logger.error(f"최대 재연결 시도 횟수 초과 ({self._max_reconnect_attempts}회)")
            self._reconnect_attempts = 0  # 초기화
            return False
        
        self._reconnect_attempts += 1
        logger.info(f"윈도우 복구 시도 {self._reconnect_attempts}/{self._max_reconnect_attempts}")
        
        try:
            # 잘시 대기 후 윈도우 핸들 확인 (불안정한 상태 대비)
            time.sleep(0.2)
            handles = self.driver.window_handles
            
            if handles:
                # 가장 최근 윈도우로 전환 시도
                target_handle = handles[-1]
                self.driver.switch_to.window(target_handle)
                
                # 전환 후 실제로 접근 가능한지 확인
                try:
                    _ = self.driver.title
                    logger.info(f"윈도우 자동 복구됨: {target_handle[:20]}...")
                    self._reconnect_attempts = 0
                    return True
                except Exception:
                    # 이 윈도우도 문제가 있으면 다른 윈도우 시도
                    for handle in reversed(handles[:-1]):
                        try:
                            self.driver.switch_to.window(handle)
                            _ = self.driver.title
                            logger.info(f"대체 윈도우로 복구됨: {handle[:20]}...")
                            self._reconnect_attempts = 0
                            return True
                        except Exception:
                            continue
                    return False
            else:
                logger.warning("사용 가능한 윈도우 없음")
                return False
        except WebDriverException as e:
            error_msg = str(e).lower()
            if any(keyword in error_msg for keyword in ['disconnected', 'not reachable', 'session deleted']):
                logger.error(f"브라우저 연결 끊김 (복구 불가): {e}")
                self.driver = None
                return False
            logger.warning(f"윈도우 복구 중 오류: {e}")
            return False
        except Exception as e:
            logger.error(f"윈도우 복구 실패: {e}")
            self.driver = None
            return False
    
    def ensure_valid_window(self) -> bool:
        """유효한 윈도우 상태 보장 (외부에서 호출 가능)"""
        return self.is_alive()
    
    def navigate(self, url: str):
        """URL 이동"""
        if self.driver and url:
            if not url.startswith('http'):
                url = 'https://' + url
            logger.info(f"URL 이동: {url}")
            self.driver.get(url)
            self.current_frame_path = ""
            self.frame_cache = []
    
    # ========== iframe 관련 메서드 ==========
    
    def get_all_frames(self, max_depth: int = 5) -> List[Dict]:
        """모든 iframe을 재귀적으로 탐색 (인터파크 중첩 iframe 지원)"""
        if not self.is_alive():
            return []
        
        frames = []
        
        def _scan_frames(parent_path: str = "", depth: int = 0):
            if depth >= max_depth:
                return
            
            try:
                iframes = self.driver.find_elements(By.TAG_NAME, 'iframe')
                logger.debug(f"[depth={depth}] iframe {len(iframes)}개 발견 (path: {parent_path or 'main'})")
                
                for i, iframe in enumerate(iframes):
                    try:
                        frame_id = iframe.get_attribute('id') or ''
                        frame_name = iframe.get_attribute('name') or ''
                        frame_src = iframe.get_attribute('src') or ''
                        
                        # 프레임 식별자 결정
                        identifier = frame_id or frame_name or f'frame_{i}'
                        current_path = f"{parent_path}/{identifier}" if parent_path else identifier
                        
                        # 인터파크 특수 프레임 체크
                        is_seat_frame = 'seat' in identifier.lower() or 'ifrm' in identifier.lower()
                        
                        frame_info = {
                            'id': frame_id,
                            'name': frame_name,
                            'src': frame_src[:100] if frame_src else '',
                            'path': current_path,
                            'depth': depth,
                            'identifier': identifier,
                            'is_special': is_seat_frame
                        }
                        frames.append(frame_info)
                        logger.debug(f"  프레임 발견: {identifier} (특수: {is_seat_frame})")
                        
                        # 해당 iframe으로 전환 후 내부 검색
                        self.driver.switch_to.frame(iframe)
                        _scan_frames(current_path, depth + 1)
                        self.driver.switch_to.parent_frame()
                        
                    except StaleElementReferenceException:
                        logger.warning(f"프레임 {i} stale 상태")
                        continue
                    except Exception as e:
                        logger.debug(f"프레임 {i} 처리 오류: {e}")
                        try:
                            self.driver.switch_to.parent_frame()
                        except:
                            pass
                        
            except Exception as e:
                logger.error(f"프레임 스캔 오류 (depth={depth}): {e}")
        
        try:
            self.driver.switch_to.default_content()
            _scan_frames()
            self.driver.switch_to.default_content()
            self.frame_cache = frames
            logger.info(f"총 {len(frames)}개 프레임 발견")
        except Exception as e:
            logger.error(f"프레임 스캔 전체 오류: {e}")
        
        return frames
    
    def switch_to_frame_by_path(self, frame_path: str) -> bool:
        """프레임 경로로 전환 (예: 'ifrmSeat/ifrmSeatDetail')"""
        if not self.is_alive():
            return False
        
        try:
            self.driver.switch_to.default_content()
            
            if not frame_path or frame_path == 'main':
                self.current_frame_path = ""
                return True
            
            parts = frame_path.split('/')
            for part in parts:
                if not part:
                    continue
                    
                # ID 또는 name으로 프레임 탐색
                try:
                    self.driver.switch_to.frame(part)
                except NoSuchFrameException:
                    # 요소로 시도
                    iframes = self.driver.find_elements(By.TAG_NAME, 'iframe')
                    found = False
                    for iframe in iframes:
                        if iframe.get_attribute('id') == part or iframe.get_attribute('name') == part:
                            self.driver.switch_to.frame(iframe)
                            found = True
                            break
                    if not found:
                        logger.warning(f"프레임 '{part}' 찾을 수 없음")
                        self.driver.switch_to.default_content()
                        return False
            
            self.current_frame_path = frame_path
            logger.debug(f"프레임 전환 성공: {frame_path}")
            return True
            
        except Exception as e:
            logger.error(f"프레임 전환 실패 ({frame_path}): {e}")
            try:
                self.driver.switch_to.default_content()
            except:
                pass
            return False
    
    def find_element_in_all_frames(self, xpath: str, max_depth: int = 5) -> Tuple[Optional[Any], str]:
        """모든 프레임에서 요소 검색, (element, frame_path) 반환"""
        if not self.is_alive():
            return None, ""
        
        def _search_frames(parent_path: str = "", depth: int = 0):
            if depth >= max_depth:
                return None, ""
            
            # 현재 프레임에서 검색
            try:
                if xpath.startswith('/') or xpath.startswith('('):
                    elements = self.driver.find_elements(By.XPATH, xpath)
                else:
                    elements = self.driver.find_elements(By.ID, xpath)
                    if not elements:
                        elements = self.driver.find_elements(By.NAME, xpath)
                
                if elements:
                    return elements[0], parent_path or 'main'
            except Exception as e:
                logger.debug(f"검색 오류 ({parent_path}): {e}")
            
            # 하위 iframe 검색
            try:
                iframes = self.driver.find_elements(By.TAG_NAME, 'iframe')
                for i, iframe in enumerate(iframes):
                    try:
                        frame_id = iframe.get_attribute('id') or iframe.get_attribute('name') or f'frame_{i}'
                        current_path = f"{parent_path}/{frame_id}" if parent_path else frame_id
                        
                        self.driver.switch_to.frame(iframe)
                        result, path = _search_frames(current_path, depth + 1)
                        
                        if result:
                            return result, path
                        
                        self.driver.switch_to.parent_frame()
                    except:
                        try:
                            self.driver.switch_to.parent_frame()
                        except:
                            pass
            except Exception as e:
                logger.debug(f"하위 프레임 검색 오류: {e}")
            
            return None, ""
        
        try:
            self.driver.switch_to.default_content()
            result, path = _search_frames()
            self.driver.switch_to.default_content()
            return result, path
        except Exception as e:
            logger.error(f"요소 검색 전체 오류: {e}")
            return None, ""
    
    def get_windows(self) -> List[Dict]:
        """열린 윈도우 목록 - 안정적인 방식으로 조회"""
        if not self.driver:
            return []
        
        windows = []
        
        try:
            handles = self.driver.window_handles
            if not handles:
                return []
            
            # 현재 윈도우 핸들 (없으면 첫 번째로)
            try:
                current = self.driver.current_window_handle
            except:
                current = handles[0] if handles else None
                if current:
                    try:
                        self.driver.switch_to.window(current)
                    except:
                        pass
            
            for handle in handles:
                try:
                    self.driver.switch_to.window(handle)
                    title = self.driver.title or "(제목 없음)"
                    windows.append({
                        'handle': handle,
                        'title': title[:35],
                        'url': self.driver.current_url,
                        'current': handle == current
                    })
                except NoSuchWindowException:
                    # 이 윈도우는 닫힘 - 건너뜀
                    logger.debug(f"윈도우 닫힘: {handle[:15]}...")
                    continue
                except Exception as e:
                    logger.debug(f"윈도우 조회 오류: {e}")
                    continue
            
            # 원래 윈도우로 복귀 시도
            if current and current in handles:
                try:
                    self.driver.switch_to.window(current)
                except:
                    # 원래 윈도우가 닫혔으면 첫 번째로
                    if windows:
                        try:
                            self.driver.switch_to.window(windows[0]['handle'])
                        except:
                            pass
            elif windows:
                # 현재 윈도우가 없으면 첫 번째로
                try:
                    self.driver.switch_to.window(windows[0]['handle'])
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"윈도우 목록 조회 오류: {e}")
        
        return windows
    
    def switch_window(self, handle: str) -> bool:
        """윈도우 전환 - 실패시 대체 윈도우로 전환"""
        if not self.driver:
            return False
        
        try:
            self.driver.switch_to.window(handle)
            self.current_frame_path = ""  # 프레임 경로 초기화
            logger.debug(f"윈도우 전환: {handle[:20]}...")
            return True
        except NoSuchWindowException:
            logger.warning(f"윈도우 없음: {handle[:20]}..., 복구 시도...")
            # 해당 윈도우가 닫혔으면 다른 윈도우로
            return self._recover_to_available_window()
        except Exception as e:
            logger.error(f"윈도우 전환 오류: {e}")
            return self._recover_to_available_window()
    
    def start_picker(self, overlay_mode: bool = False) -> bool:
        """요소 선택 모드 시작 - 모든 iframe에 주입
        
        Args:
            overlay_mode: True면 오버레이 모드 (실제 요소와 상호작용 차단)
        """
        if not self.is_alive():
            return False
        
        script = self.PICKER_SCRIPT_OVERLAY if overlay_mode else self.PICKER_SCRIPT
        injected_count = 0
        
        def _inject_to_frames(depth: int = 0, max_depth: int = 5, path: str = ""):
            nonlocal injected_count
            if depth >= max_depth:
                return
            
            try:
                # 현재 프레임에 주입
                result = self.driver.execute_script(script)
                if result == "OK":
                    injected_count += 1
                    logger.debug(f"Picker 주입 성공: {path or 'main'} (overlay={overlay_mode})")
                
                # 하위 iframe에도 주입
                iframes = self.driver.find_elements(By.TAG_NAME, 'iframe')
                for i, iframe in enumerate(iframes):
                    try:
                        frame_id = iframe.get_attribute('id') or iframe.get_attribute('name') or f'frame_{i}'
                        current_path = f"{path}/{frame_id}" if path else frame_id
                        
                        self.driver.switch_to.frame(iframe)
                        _inject_to_frames(depth + 1, max_depth, current_path)
                        self.driver.switch_to.parent_frame()
                    except Exception as e:
                        logger.debug(f"iframe 주입 오류 ({frame_id}): {e}")
                        try:
                            self.driver.switch_to.parent_frame()
                        except:
                            pass
            except Exception as e:
                logger.debug(f"Picker 주입 오류 (path={path}): {e}")
        
        try:
            self.driver.switch_to.default_content()
            _inject_to_frames()
            self.driver.switch_to.default_content()
            
            mode_str = "오버레이" if overlay_mode else "일반"
            logger.info(f"Picker 주입 완료: {injected_count}개 프레임 ({mode_str} 모드)")
            return injected_count > 0
        except Exception as e:
            logger.error(f"Picker 시작 오류: {e}")
            return False
    
    def get_picker_result(self) -> Optional[Dict]:
        """선택 결과 가져오기 - 모든 프레임에서 검색"""
        if not self.is_alive():
            return None
        
        def _check_frames(path: str = "", depth: int = 0, max_depth: int = 5):
            if depth >= max_depth:
                return None
            
            try:
                result = self.driver.execute_script("return window.__pickerResult;")
                if result:
                    self.driver.execute_script("window.__pickerResult = null;")
                    result['frame_path'] = path or 'main'  # 프레임 경로 추가
                    logger.debug(f"Picker 결과 발견: {path or 'main'}")
                    return result
                
                # 하위 iframe 검색
                iframes = self.driver.find_elements(By.TAG_NAME, 'iframe')
                for i, iframe in enumerate(iframes):
                    try:
                        frame_id = iframe.get_attribute('id') or iframe.get_attribute('name') or f'frame_{i}'
                        current_path = f"{path}/{frame_id}" if path else frame_id
                        
                        self.driver.switch_to.frame(iframe)
                        result = _check_frames(current_path, depth + 1, max_depth)
                        
                        if result:
                            return result
                        
                        self.driver.switch_to.parent_frame()
                    except:
                        try:
                            self.driver.switch_to.parent_frame()
                        except:
                            pass
            except Exception as e:
                logger.debug(f"결과 검색 오류 (path={path}): {e}")
            
            return None
        
        try:
            self.driver.switch_to.default_content()
            result = _check_frames()
            self.driver.switch_to.default_content()
            return result
        except:
            return None
    
    def is_picker_active(self) -> bool:
        """선택 모드 활성화 여부 - 모든 프레임 검사"""
        if not self.is_alive():
            return False
        
        def _check_active(depth: int = 0, max_depth: int = 5):
            if depth >= max_depth:
                return False
            
            try:
                if self.driver.execute_script("return window.__pickerActive || false;"):
                    return True
                
                iframes = self.driver.find_elements(By.TAG_NAME, 'iframe')
                for iframe in iframes:
                    try:
                        self.driver.switch_to.frame(iframe)
                        if _check_active(depth + 1, max_depth):
                            return True
                        self.driver.switch_to.parent_frame()
                    except:
                        try:
                            self.driver.switch_to.parent_frame()
                        except:
                            pass
            except:
                pass
            
            return False
        
        try:
            self.driver.switch_to.default_content()
            result = _check_active()
            self.driver.switch_to.default_content()
            return result
        except:
            return False
    
    def highlight(self, xpath: str, duration: int = 2500, frame_path: str = None) -> bool:
        """요소 하이라이트 - 중첩 iframe 지원"""
        if not self.is_alive():
            return False
        
        try:
            # frame_path가 주어진 경우 해당 프레임으로 이동
            if frame_path and frame_path != 'main':
                if not self.switch_to_frame_by_path(frame_path):
                    logger.warning(f"프레임 전환 실패: {frame_path}")
            
            # find_element_in_all_frames 사용
            element, found_path = self.find_element_in_all_frames(xpath)
            
            if element:
                # 해당 프레임으로 이동 후 하이라이트
                self.switch_to_frame_by_path(found_path)
                
                self.driver.execute_script(f'''
                    var el = arguments[0];
                    var orig = el.getAttribute('style') || '';
                    el.style.cssText += ';border: 4px solid #00ff88 !important; background-color: rgba(0,255,136,0.25) !important; box-shadow: 0 0 30px #00ff88 !important;';
                    el.scrollIntoView({{block: 'center', behavior: 'smooth'}});
                    setTimeout(function() {{ el.setAttribute('style', orig); }}, {duration});
                ''', element)
                
                logger.info(f"하이라이트 완료: {xpath} (프레임: {found_path})")
                self.driver.switch_to.default_content()
                return True
            
            logger.warning(f"하이라이트 요소 못찾음: {xpath}")
            self.driver.switch_to.default_content()
            return False
            
        except Exception as e:
            logger.error(f"하이라이트 오류: {e}")
            try:
                self.driver.switch_to.default_content()
            except:
                pass
            return False
    
    def validate_xpath(self, xpath: str) -> Dict:
        """XPath 검증 - 중첩 iframe 재귀 탐색"""
        result = {'found': False, 'count': 0, 'tag': '', 'text': '', 'frame': 'main', 'frame_path': '', 'error': ''}
        
        if not self.is_alive():
            result['error'] = "브라우저 미연결"
            return result
        
        def _search_frames(parent_path: str = "", depth: int = 0, max_depth: int = 5):
            if depth >= max_depth:
                return None, 0
            
            # 현재 프레임에서 검색
            try:
                if xpath.startswith('/') or xpath.startswith('('):
                    elements = self.driver.find_elements(By.XPATH, xpath)
                else:
                    elements = self.driver.find_elements(By.ID, xpath)
                    if not elements:
                        elements = self.driver.find_elements(By.NAME, xpath)
                
                if elements:
                    return elements, parent_path or 'main'
            except Exception as e:
                logger.debug(f"검색 오류 ({parent_path}): {e}")
            
            # 하위 iframe 검색
            try:
                iframes = self.driver.find_elements(By.TAG_NAME, 'iframe')
                for i, iframe in enumerate(iframes):
                    try:
                        frame_id = iframe.get_attribute('id') or iframe.get_attribute('name') or f'frame_{i}'
                        current_path = f"{parent_path}/{frame_id}" if parent_path else frame_id
                        
                        self.driver.switch_to.frame(iframe)
                        found_elements, found_path = _search_frames(current_path, depth + 1, max_depth)
                        
                        if found_elements:
                            return found_elements, found_path
                        
                        self.driver.switch_to.parent_frame()
                    except StaleElementReferenceException:
                        continue
                    except:
                        try:
                            self.driver.switch_to.parent_frame()
                        except:
                            pass
            except Exception as e:
                logger.debug(f"하위 프레임 검색 오류: {e}")
            
            return None, ""
        
        try:
            self.driver.switch_to.default_content()
            elements, frame_path = _search_frames()
            self.driver.switch_to.default_content()
            
            if elements:
                result['found'] = True
                result['count'] = len(elements)
                result['tag'] = elements[0].tag_name
                result['text'] = (elements[0].text or elements[0].get_attribute('value') or '')[:60]
                result['frame'] = frame_path.split('/')[-1] if '/' in frame_path else frame_path
                result['frame_path'] = frame_path
                logger.debug(f"XPath 검증 성공: {xpath} (프레임: {frame_path})")
            else:
                logger.debug(f"XPath 검증 실패: {xpath}")
            
            return result
            
        except Exception as e:
            logger.error(f"XPath 검증 오류: {e}")
            result['error'] = str(e)
            return result


# ============================================================================
# 워커 스레드
# ============================================================================

class PickerWatcher(QThread):
    """요소 선택 감시"""
    
    picked = pyqtSignal(dict)
    cancelled = pyqtSignal()
    
    def __init__(self, browser: BrowserManager):
        super().__init__()
        self.browser = browser
        self._running = True
    
    def stop(self):
        self._running = False
    
    def run(self):
        while self._running:
            result = self.browser.get_picker_result()
            if result:
                if result.get('cancelled'):
                    self.cancelled.emit()
                else:
                    self.picked.emit(result)
                break
            
            if not self.browser.is_picker_active():
                self.cancelled.emit()
                break
            
            time.sleep(0.1)


class ValidateWorker(QThread):
    """검증 워커"""
    
    progress = pyqtSignal(int, str)
    validated = pyqtSignal(str, dict)
    finished = pyqtSignal(int, int)  # found, total
    
    def __init__(self, browser: BrowserManager, items: List[XPathItem], handles: List[str]):
        super().__init__()
        self.browser = browser
        self.items = items
        self.handles = handles or []
        self._cancelled = False
    
    def cancel(self):
        self._cancelled = True
    
    def run(self):
        if not self.handles:
            try:
                self.handles = [self.browser.driver.current_window_handle]
            except:
                self.finished.emit(0, 0)
                return
        
        total = len(self.items) * len(self.handles)
        current = 0
        found_count = 0
        
        for handle in self.handles:
            if self._cancelled:
                break
            
            try:
                self.browser.switch_window(handle)
                win_title = self.browser.driver.title[:15]
            except:
                continue
            
            for item in self.items:
                if self._cancelled:
                    break
                
                current += 1
                self.progress.emit(int(current / total * 100), f"[{win_title}] {item.name}")
                
                result = self.browser.validate_xpath(item.xpath)
                result['window'] = win_title
                
                if result['found']:
                    found_count += 1
                
                self.validated.emit(item.name, result)
                time.sleep(0.03)
        
        self.finished.emit(found_count, len(self.items))


# ============================================================================
# 메인 윈도우
# ============================================================================

class XPathExplorer(QMainWindow):
    """XPath 탐색기 메인"""
    
    def __init__(self):
        super().__init__()
        
        self.browser = BrowserManager()
        self.config = SiteConfig.from_preset("인터파크")
        self.picker_watcher: Optional[PickerWatcher] = None
        self.validate_worker: Optional[ValidateWorker] = None
        
        # Phase 3: XPath 히스토리
        self.xpath_history: List[Dict[str, str]] = []
        self.max_history = Config.MAX_HISTORY
        
        # Phase 3: 쿠키 관리
        self.cookie_dir = Path.home() / '.xpath_explorer' / 'cookies'
        self.cookie_dir.mkdir(parents=True, exist_ok=True)
        
        self.settings = QSettings("XPathExplorer", "v3")
        
        self._init_ui()
        self._setup_timers()
        self._load_settings()
        self._load_xpath_history()
    
    def _init_ui(self):
        """UI 초기화"""
        self.setWindowTitle(f"🎯 {Config.APP_NAME} v{Config.VERSION}")
        self.setGeometry(50, 50, Config.WINDOW_WIDTH, Config.WINDOW_HEIGHT)
        self.setStyleSheet(STYLE)
        
        # 메뉴
        self._create_menu()
        
        # 단축키 등록 (UI 쩌거 없이 전역으로 동작)
        self._setup_shortcuts()
        
        # 중앙 위젯
        central = QWidget()
        self.setCentralWidget(central)
        
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # Toast 알림 위젯
        self.toast = ToastWidget(central)
        
        # 상단: 브라우저 컨트롤
        main_layout.addWidget(self._create_browser_panel())
        
        # 중간: 메인 영역
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._create_list_panel())
        splitter.addWidget(self._create_editor_panel())
        splitter.setSizes([550, 1000])
        main_layout.addWidget(splitter, 1)
        
        # 하단: 상태
        main_layout.addWidget(self._create_status_panel())
        
        self.statusBar().showMessage("🚀 시작하려면 브라우저를 열어주세요")
    
    def _setup_shortcuts(self):
        """단축키 등록"""
        # 폰트 크기 단축키
        QShortcut(QKeySequence("Ctrl++"), self, self._increase_font)
        QShortcut(QKeySequence("Ctrl+="), self, self._increase_font)  # Shift 없이 +
        QShortcut(QKeySequence("Ctrl+-"), self, self._decrease_font)
        QShortcut(QKeySequence("Ctrl+0"), self, self._reset_font)
    
    def _create_menu(self):
        """메뉴바"""
        menubar = self.menuBar()
        
        # 파일
        file_menu = menubar.addMenu("파일(&F)")
        
        new_action = file_menu.addAction("새 설정")
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self._new_config)
        
        open_action = file_menu.addAction("설정 열기...")
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._open_config)
        
        save_action = file_menu.addAction("설정 저장...")
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._save_config)
        
        file_menu.addSeparator()
        
        # 내보내기 서브메뉴
        export_menu = file_menu.addMenu("📤 내보내기")
        export_menu.addAction("JSON").triggered.connect(lambda: self._export('json'))
        export_menu.addAction("Python 딕셔너리").triggered.connect(lambda: self._export('dict'))
        export_menu.addAction("Python 클래스").triggered.connect(lambda: self._export('class'))
        export_menu.addAction("YAML").triggered.connect(lambda: self._export('yaml'))
        
        file_menu.addSeparator()
        file_menu.addAction("종료").triggered.connect(self.close)
        
        # 도구
        tools_menu = menubar.addMenu("도구(&T)")
        
        validate_action = tools_menu.addAction("전체 검증")
        validate_action.setShortcut("F5")
        validate_action.triggered.connect(self._validate_all)
        
        tools_menu.addAction("페이지 분석").triggered.connect(self._analyze_page)
        
        tools_menu.addSeparator()
        
        # 쿠키 관리
        cookie_menu = tools_menu.addMenu("🍪 쿠키 관리")
        cookie_menu.addAction("쿠키 저장...").triggered.connect(self._save_cookies)
        cookie_menu.addAction("쿠키 불러오기...").triggered.connect(self._load_cookies)
        cookie_menu.addAction("현재 쿠키 삭제").triggered.connect(self._clear_cookies)
        
        tools_menu.addSeparator()
        
        # XPath 히스토리
        tools_menu.addAction("📜 XPath 히스토리").triggered.connect(self._show_xpath_history)
        
        # 보기
        view_menu = menubar.addMenu("보기(&V)")
        view_menu.addAction("폰트 크기 증가 (Ctrl++)").triggered.connect(self._increase_font)
        view_menu.addAction("폰트 크기 감소 (Ctrl+-)").triggered.connect(self._decrease_font)
        view_menu.addAction("폰트 크기 초기화").triggered.connect(self._reset_font)
        
        # 도움말
        help_menu = menubar.addMenu("도움말(&H)")
        help_menu.addAction("단축키 목록").triggered.connect(self._show_shortcuts)
        help_menu.addAction("정보...").triggered.connect(self._show_about)
    
    def _create_browser_panel(self) -> QWidget:
        """브라우저 컨트롤 패널"""
        panel = QFrame()
        panel.setStyleSheet("QFrame { background-color: #1b263b; border-radius: 12px; padding: 10px; }")
        
        layout = QHBoxLayout(panel)
        layout.setSpacing(15)
        
        # 브라우저 버튼
        self.btn_browser = QPushButton("🌐 브라우저 열기")
        self.btn_browser.setObjectName("primary")
        self.btn_browser.setMinimumWidth(150)
        self.btn_browser.clicked.connect(self._toggle_browser)
        layout.addWidget(self.btn_browser)
        
        # 프리셋 선택
        layout.addWidget(QLabel("사이트:"))
        self.combo_preset = QComboBox()
        self.combo_preset.addItems(list(SITE_PRESETS.keys()))
        self.combo_preset.setMinimumWidth(130)
        self.combo_preset.currentTextChanged.connect(self._on_preset_changed)
        layout.addWidget(self.combo_preset)
        
        # URL
        self.input_url = QLineEdit()
        self.input_url.setPlaceholderText("URL 입력...")
        self.input_url.setText(self.config.url)
        self.input_url.returnPressed.connect(self._navigate)
        layout.addWidget(self.input_url, 1)
        
        btn_go = QPushButton("이동")
        btn_go.clicked.connect(self._navigate)
        layout.addWidget(btn_go)
        
        # 윈도우 선택
        layout.addWidget(QLabel("│  창:"))
        self.combo_windows = QComboBox()
        self.combo_windows.setMinimumWidth(150)
        self.combo_windows.currentIndexChanged.connect(self._on_window_changed)
        layout.addWidget(self.combo_windows)
        
        btn_refresh = QPushButton("🔄")
        btn_refresh.setMaximumWidth(45)
        btn_refresh.setToolTip("창 목록 새로고침")
        btn_refresh.clicked.connect(self._refresh_windows)
        layout.addWidget(btn_refresh)
        
        # iframe 선택 (인터파크 좌석 iframe 지원)
        layout.addWidget(QLabel("│  프레임:"))
        self.combo_frames = QComboBox()
        self.combo_frames.setMinimumWidth(150)
        self.combo_frames.addItem("🖼️ main (기본)")
        self.combo_frames.setToolTip("현재 페이지의 iframe 목록")
        layout.addWidget(self.combo_frames)
        
        btn_scan_frames = QPushButton("🔍")
        btn_scan_frames.setMaximumWidth(45)
        btn_scan_frames.setToolTip("iframe 목록 스캔 (인터파크 좌석선택창 감지)")
        btn_scan_frames.clicked.connect(self._scan_frames)
        layout.addWidget(btn_scan_frames)
        
        # 상태 표시
        layout.addWidget(QLabel("│"))
        self.lbl_status = QLabel("● 대기 중")
        self.lbl_status.setObjectName("status_disconnected")
        layout.addWidget(self.lbl_status)
        
        return panel
    
    def _create_list_panel(self) -> QWidget:
        """XPath 목록 패널"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 10, 0)
        
        # 헤더
        header = QHBoxLayout()
        title = QLabel("📋 XPath 목록")
        title.setObjectName("title")
        header.addWidget(title)
        header.addStretch()
        
        btn_add = QPushButton("+ 새 항목")
        btn_add.setObjectName("success")
        btn_add.clicked.connect(self._add_new_item)
        header.addWidget(btn_add)
        
        layout.addLayout(header)
        
        # 필터
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("카테고리:"))
        
        self.combo_filter = QComboBox()
        self.combo_filter.addItem("전체")
        self.combo_filter.currentTextChanged.connect(self._filter_items)
        filter_layout.addWidget(self.combo_filter, 1)
        
        layout.addLayout(filter_layout)
        
        # 테이블
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["", "이름", "카테고리", "설명", ""])
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        
        self.table.setColumnWidth(0, 45)
        self.table.setColumnWidth(1, 140)
        self.table.setColumnWidth(2, 85)
        self.table.setColumnWidth(4, 45)
        
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.itemSelectionChanged.connect(self._on_item_selected)
        self.table.itemDoubleClicked.connect(self._on_item_double_clicked)  # 더블클릭으로 XPath 테스트
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        
        layout.addWidget(self.table)
        
        # 요약
        self.lbl_summary = QLabel("총 0개")
        self.lbl_summary.setObjectName("subtitle")
        layout.addWidget(self.lbl_summary)
        
        # 초기화
        self._refresh_table()
        
        return panel
    
    def _create_editor_panel(self) -> QWidget:
        """편집기 패널"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 0, 0, 0)
        layout.setSpacing(15)
        
        # === 요소 선택 버튼 (핵심!) ===
        pick_frame = QFrame()
        pick_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1b263b, stop:1 #0d1b2a);
                border: 2px solid #9b59b6;
                border-radius: 15px;
                padding: 20px;
            }
        """)
        pick_layout = QVBoxLayout(pick_frame)
        
        pick_title = QLabel("🎯 브라우저에서 요소 선택")
        pick_title.setStyleSheet("font-size: 14pt; font-weight: bold; color: #9b59b6; border: none;")
        pick_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pick_layout.addWidget(pick_title)
        
        pick_desc = QLabel("버튼을 클릭한 후 브라우저에서 원하는 요소를 클릭하세요")
        pick_desc.setStyleSheet("color: #778da9; border: none;")
        pick_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pick_layout.addWidget(pick_desc)
        
        self.btn_pick = QPushButton("🎯 요소 선택 시작")
        self.btn_pick.setObjectName("picker")
        self.btn_pick.setEnabled(False)
        self.btn_pick.clicked.connect(self._start_picker)
        pick_layout.addWidget(self.btn_pick)
        
        # 오버레이 모드 옵션
        overlay_row = QHBoxLayout()
        overlay_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.chk_overlay = QCheckBox("🛡️ 오버레이 모드")
        self.chk_overlay.setToolTip("체크하면 요소와 상호작용하지 않고 선택만 가능 (실수로 클릭 방지)")
        self.chk_overlay.setStyleSheet("color: #e74c3c; border: none; font-weight: bold;")
        overlay_row.addWidget(self.chk_overlay)
        pick_layout.addLayout(overlay_row)
        
        layout.addWidget(pick_frame)
        
        # === 편집기 ===
        edit_group = QGroupBox("✏️ XPath 편집")
        edit_layout = QVBoxLayout(edit_group)
        
        # 이름 & 카테고리
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("이름:"))
        self.input_name = QLineEdit()
        self.input_name.setPlaceholderText("예: login_button")
        row1.addWidget(self.input_name, 1)
        
        row1.addWidget(QLabel("카테고리:"))
        self.input_category = QComboBox()
        self.input_category.setEditable(True)
        self.input_category.addItems(["login", "booking", "seat", "captcha", "district", "popup", "payment", "custom"])
        self.input_category.setMinimumWidth(120)
        row1.addWidget(self.input_category)
        edit_layout.addLayout(row1)
        
        # 설명
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("설명:"))
        self.input_desc = QLineEdit()
        self.input_desc.setPlaceholderText("요소 설명...")
        row2.addWidget(self.input_desc, 1)
        edit_layout.addLayout(row2)
        
        # XPath
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("XPath:"))
        self.input_xpath = QPlainTextEdit()
        self.input_xpath.setMaximumHeight(70)
        self.input_xpath.setPlaceholderText("XPath 또는 ID/Name 입력...")
        row3.addWidget(self.input_xpath, 1)
        
        xpath_btns = QVBoxLayout()
        btn_test = QPushButton("▶")
        btn_test.setMaximumWidth(40)
        btn_test.setToolTip("테스트")
        btn_test.clicked.connect(self._test_xpath)
        xpath_btns.addWidget(btn_test)
        
        btn_hl = QPushButton("🔦")
        btn_hl.setMaximumWidth(40)
        btn_hl.setToolTip("하이라이트")
        btn_hl.clicked.connect(self._highlight_xpath)
        xpath_btns.addWidget(btn_hl)
        
        row3.addLayout(xpath_btns)
        edit_layout.addLayout(row3)
        
        # CSS
        row4 = QHBoxLayout()
        row4.addWidget(QLabel("CSS:"))
        self.input_css = QLineEdit()
        self.input_css.setPlaceholderText("CSS 선택자 (자동 생성)")
        row4.addWidget(self.input_css, 1)
        edit_layout.addLayout(row4)
        
        # 버튼
        btn_row = QHBoxLayout()
        
        self.btn_save = QPushButton("💾 저장")
        self.btn_save.setObjectName("success")
        self.btn_save.clicked.connect(self._save_item)
        btn_row.addWidget(self.btn_save)
        
        btn_clear = QPushButton("🗑️ 지우기")
        btn_clear.clicked.connect(self._clear_editor)
        btn_row.addWidget(btn_clear)
        
        btn_row.addStretch()
        
        btn_validate = QPushButton("✓ 전체 검증")
        btn_validate.clicked.connect(self._validate_all)
        btn_row.addWidget(btn_validate)
        
        edit_layout.addLayout(btn_row)
        layout.addWidget(edit_group)
        
        # === 결과 표시 ===
        result_group = QGroupBox("📊 결과")
        result_layout = QVBoxLayout(result_group)
        
        self.txt_result = QTextEdit()
        self.txt_result.setReadOnly(True)
        self.txt_result.setMaximumHeight(180)
        self.txt_result.setStyleSheet("font-family: 'Consolas', monospace; font-size: 10pt;")
        result_layout.addWidget(self.txt_result)
        
        layout.addWidget(result_group, 1)
        
        return panel
    
    def _create_status_panel(self) -> QWidget:
        """상태 패널"""
        panel = QFrame()
        panel.setStyleSheet("QFrame { background-color: #1b263b; border-radius: 8px; padding: 5px; }")
        
        layout = QHBoxLayout(panel)
        
        self.progress = QProgressBar()
        self.progress.setMaximumWidth(300)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        
        self.lbl_progress = QLabel("")
        self.lbl_progress.setStyleSheet("color: #778da9;")
        layout.addWidget(self.lbl_progress, 1)
        
        return panel
    
    def _setup_timers(self):
        """타이머 설정"""
        self.check_timer = QTimer()
        self.check_timer.timeout.connect(self._check_browser)
        self.check_timer.start(Config.CHECK_INTERVAL_MS)
    
    def _check_browser(self):
        """브라우저 상태 체크 - 연결 상태 변경 감지"""
        was_connected = getattr(self, '_was_browser_connected', False)
        
        try:
            is_connected = self.browser.is_alive()
        except Exception as e:
            logger.error(f"브라우저 상태 체크 오류: {e}")
            is_connected = False
        
        if is_connected:
            self.lbl_status.setText("● 연결됨")
            self.lbl_status.setObjectName("status_connected")
            self.btn_pick.setEnabled(True)
            self.btn_browser.setText("🌐 브라우저 닫기")
            
            # 연결 복구 감지 - Toast 알림
            if not was_connected:
                self._show_toast("브라우저 연결됨", "success")
                logger.info("브라우저 연결 상태 복구됨")
            
            # 윈도우 수 변경 감지
            try:
                win_count = len(self.browser.driver.window_handles)
                if win_count != self.combo_windows.count():
                    self._refresh_windows()
            except Exception as e:
                logger.debug(f"윈도우 핸들 확인 중 오류: {e}")
        else:
            self.lbl_status.setText("● 연결 안됨")
            self.lbl_status.setObjectName("status_disconnected")
            self.btn_pick.setEnabled(False)
            self.btn_browser.setText("🌐 브라우저 열기")
            self.combo_windows.clear()
            
            # 연결 끊김 감지 - Toast 알림
            if was_connected:
                self._show_toast("브라우저 연결 끊김", "warning")
                logger.warning("브라우저 연결 끊김 감지")
        
        self._was_browser_connected = is_connected
        
        # 스타일 새로고침
        self.lbl_status.setStyleSheet(self.lbl_status.styleSheet())
    
    # ========== 브라우저 관련 ==========
    
    def _toggle_browser(self):
        """브라우저 열기/닫기"""
        if self.browser.is_alive():
            self.browser.close()
        else:
            self.statusBar().showMessage("🌐 브라우저 시작 중...")
            QApplication.processEvents()
            
            if self.browser.create_driver(UC_AVAILABLE):
                url = self.input_url.text().strip() or self.config.url
                if url:
                    self.browser.navigate(url)
                
                if UC_AVAILABLE:
                    time.sleep(2)  # Cloudflare 대기
                
                self._refresh_windows()
                self.statusBar().showMessage("✅ 브라우저 연결됨")
            else:
                QMessageBox.critical(self, "오류", "브라우저를 열 수 없습니다.")
    
    def _navigate(self):
        """URL 이동"""
        url = self.input_url.text().strip()
        if url:
            self.browser.navigate(url)
    
    def _refresh_windows(self):
        """윈도우 목록 갱신"""
        self.combo_windows.blockSignals(True)
        self.combo_windows.clear()
        
        for i, win in enumerate(self.browser.get_windows()):
            prefix = "▶ " if win['current'] else "   "
            self.combo_windows.addItem(f"{prefix}[{i+1}] {win['title']}", win['handle'])
            if win['current']:
                self.combo_windows.setCurrentIndex(i)
        
        self.combo_windows.blockSignals(False)
    
    def _on_window_changed(self, index: int):
        """윈도우 선택 변경"""
        if index >= 0:
            handle = self.combo_windows.itemData(index)
            if handle:
                self.browser.switch_window(handle)
                try:
                    self.input_url.setText(self.browser.driver.current_url)
                except WebDriverException as e:
                    logger.warning(f"URL 가져오기 실패: {e}")
                except Exception as e:
                    logger.debug(f"URL 가져오기 중 예외: {e}")
                # 윈도우 변경 시 iframe 목록 초기화
                self._scan_frames()
    
    def _scan_frames(self):
        """현재 페이지의 iframe 스캔 (인터파크 좌석 iframe 지원)"""
        if not self.browser.is_alive():
            return
        
        self.statusBar().showMessage("🔍 iframe 스캔 중...")
        QApplication.processEvents()
        
        self.combo_frames.blockSignals(True)
        self.combo_frames.clear()
        self.combo_frames.addItem("🖼️ main (기본)", "main")
        
        frames = self.browser.get_all_frames()
        
        for frame in frames:
            indent = "  " * frame['depth']
            icon = "⭐" if frame['is_special'] else "📄"  # 인터파크 특수 프레임 표시
            label = f"{indent}{icon} {frame['identifier']}"
            self.combo_frames.addItem(label, frame['path'])
        
        self.combo_frames.blockSignals(False)
        
        special_count = sum(1 for f in frames if f['is_special'])
        msg = f"✅ {len(frames)}개 iframe 발견"
        if special_count > 0:
            msg += f" (⭐ 좌석 관련: {special_count}개)"
        
        self.statusBar().showMessage(msg)
        logger.info(msg)
    
    # ========== 프리셋 ==========
    
    def _on_preset_changed(self, preset_name: str):
        """프리셋 변경"""
        if preset_name in SITE_PRESETS:
            reply = QMessageBox.question(
                self, "프리셋 변경",
                f"'{preset_name}' 프리셋으로 변경하시겠습니까?\n현재 설정이 초기화됩니다.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.config = SiteConfig.from_preset(preset_name)
                self.input_url.setText(self.config.url)
                self._refresh_table()
                self._clear_editor()
                self.statusBar().showMessage(f"✅ '{preset_name}' 프리셋 로드됨")
    
    # ========== 테이블 ==========
    
    def _refresh_table(self, filter_cat: str = "전체"):
        """테이블 갱신"""
        self.table.setRowCount(0)
        
        # 카테고리 필터 업데이트
        categories = ["전체"] + sorted(set(item.category for item in self.config.items))
        current_filter = self.combo_filter.currentText()
        self.combo_filter.blockSignals(True)
        self.combo_filter.clear()
        self.combo_filter.addItems(categories)
        if current_filter in categories:
            self.combo_filter.setCurrentText(current_filter)
        self.combo_filter.blockSignals(False)
        
        # 필터링
        items = self.config.items
        if filter_cat != "전체":
            items = [item for item in items if item.category == filter_cat]
        
        verified = 0
        for item in items:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # 상태
            status = "✅" if item.is_verified else "⬜"
            if item.is_verified:
                verified += 1
            
            status_item = QTableWidgetItem(status)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 0, status_item)
            
            # 이름
            name_item = QTableWidgetItem(item.name)
            name_item.setData(Qt.ItemDataRole.UserRole, item.name)
            self.table.setItem(row, 1, name_item)
            
            # 카테고리
            self.table.setItem(row, 2, QTableWidgetItem(item.category))
            
            # 설명
            self.table.setItem(row, 3, QTableWidgetItem(item.description))
            
            # 삭제 버튼
            btn_del = QPushButton("✕")
            btn_del.setStyleSheet("background: #ef476f; border-radius: 4px; padding: 5px;")
            btn_del.clicked.connect(lambda _, n=item.name: self._delete_item(n))
            self.table.setCellWidget(row, 4, btn_del)
        
        # 요약
        total = len(items)
        self.lbl_summary.setText(f"총 {total}개  |  ✅ {verified}  ⬜ {total - verified}")
    
    def _filter_items(self, category: str):
        """필터링"""
        self._refresh_table(category)
    
    def _on_item_selected(self):
        """항목 선택"""
        selected = self.table.selectedItems()
        if not selected:
            return
        
        name_item = self.table.item(selected[0].row(), 1)
        if name_item:
            name = name_item.data(Qt.ItemDataRole.UserRole)
            item = self.config.get_item(name)
            if item:
                self._load_to_editor(item)
    
    def _on_item_double_clicked(self, table_item: QTableWidgetItem):
        """항목 더블클릭 - XPath 테스트 실행"""
        row = table_item.row()
        name_item = self.table.item(row, 1)
        if name_item:
            name = name_item.data(Qt.ItemDataRole.UserRole)
            item = self.config.get_item(name)
            if item:
                self._load_to_editor(item)
                self._test_xpath()  # 자동으로 XPath 테스트 실행
                self._show_toast(f"'{name}' XPath 테스트 실행됨", "info")
    
    def _load_to_editor(self, item: XPathItem):
        """편집기에 로드"""
        self.input_name.setText(item.name)
        self.input_category.setCurrentText(item.category)
        self.input_desc.setText(item.description)
        self.input_xpath.setPlainText(item.xpath)
        self.input_css.setText(item.css_selector)
        
        # 결과 표시
        if item.is_verified:
            self.txt_result.setHtml(f"""
                <div style="color: #06d6a0;">✅ <b>검증됨</b></div>
                <div style="margin-top: 10px;">
                <b>태그:</b> {item.element_tag}<br>
                <b>텍스트:</b> {item.element_text}<br>
                <b>프레임:</b> {item.found_frame or 'main'}
                </div>
            """)
        else:
            self.txt_result.setHtml("<div style='color: #778da9;'>⬜ 아직 검증되지 않음</div>")
    
    def _show_context_menu(self, pos):
        """컨텍스트 메뉴"""
        menu = QMenu(self)
        menu.addAction("테스트").triggered.connect(self._test_xpath)
        menu.addAction("하이라이트").triggered.connect(self._highlight_xpath)
        menu.addSeparator()
        menu.addAction("삭제").triggered.connect(self._delete_selected)
        menu.exec(self.table.mapToGlobal(pos))
    
    def _delete_selected(self):
        """선택 항목 삭제"""
        selected = self.table.selectedItems()
        if selected:
            name = self.table.item(selected[0].row(), 1).data(Qt.ItemDataRole.UserRole)
            self._delete_item(name)
    
    def _delete_item(self, name: str):
        """항목 삭제"""
        reply = QMessageBox.question(
            self, "삭제 확인",
            f"'{name}'을(를) 삭제하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.config.remove_item(name)
            self._refresh_table(self.combo_filter.currentText())
            self._clear_editor()
    
    def _add_new_item(self):
        """새 항목"""
        self._clear_editor()
        self.input_name.setFocus()
    
    # ========== 편집기 ==========
    
    def _clear_editor(self):
        """편집기 초기화"""
        self.input_name.clear()
        self.input_category.setCurrentIndex(0)
        self.input_desc.clear()
        self.input_xpath.clear()
        self.input_css.clear()
        self.txt_result.clear()
    
    def _save_item(self):
        """항목 저장"""
        name = self.input_name.text().strip()
        xpath = self.input_xpath.toPlainText().strip()
        
        if not name:
            QMessageBox.warning(self, "알림", "이름을 입력하세요.")
            return
        if not xpath:
            QMessageBox.warning(self, "알림", "XPath를 입력하세요.")
            return
        
        existing = self.config.get_item(name)
        
        item = XPathItem(
            name=name,
            xpath=xpath,
            category=self.input_category.currentText(),
            description=self.input_desc.text(),
            css_selector=self.input_css.text(),
            is_verified=existing.is_verified if existing else False,
            element_tag=existing.element_tag if existing else "",
            element_text=existing.element_text if existing else "",
            found_window=existing.found_window if existing else "",
            found_frame=existing.found_frame if existing else ""
        )
        
        self.config.add_or_update(item)
        self._refresh_table(self.combo_filter.currentText())
        self.statusBar().showMessage(f"💾 '{name}' 저장됨")
    
    def _test_xpath(self):
        """XPath 테스트"""
        xpath = self.input_xpath.toPlainText().strip()
        if not xpath:
            return
        
        if not self.browser.is_alive():
            QMessageBox.warning(self, "알림", "브라우저가 연결되어 있지 않습니다.")
            return
        
        result = self.browser.validate_xpath(xpath)
        
        if result['found']:
            frame_info = result.get('frame_path', result['frame'])
            self.txt_result.setHtml(f"""
                <div style="color: #06d6a0; font-size: 14pt;">✅ 발견!</div>
                <div style="margin-top: 10px;">
                <b>개수:</b> {result['count']}개<br>
                <b>태그:</b> &lt;{result['tag']}&gt;<br>
                <b>텍스트:</b> {result['text']}<br>
                <b>프레임:</b> <span style="color: #ffd166;">{frame_info}</span>
                </div>
            """)
            self.browser.highlight(xpath, frame_path=result.get('frame_path'))
        else:
            self.txt_result.setHtml(f"""
                <div style="color: #ef476f; font-size: 14pt;">❌ 찾을 수 없음</div>
                <div style="margin-top: 10px; color: #778da9;">
                {result.get('error', '요소가 존재하지 않습니다.')}
                </div>
            """)
    
    def _highlight_xpath(self):
        """하이라이트"""
        xpath = self.input_xpath.toPlainText().strip()
        if xpath and self.browser.is_alive():
            if self.browser.highlight(xpath):
                self.statusBar().showMessage("🔦 요소 하이라이트됨")
            else:
                self.statusBar().showMessage("요소를 찾을 수 없음")
    
    # ========== 요소 선택 ==========
    
    def _start_picker(self):
        """요소 선택 시작"""
        if not self.browser.is_alive():
            QMessageBox.warning(self, "알림", "브라우저가 연결되어 있지 않습니다.")
            return
        
        overlay_mode = self.chk_overlay.isChecked()
        if self.browser.start_picker(overlay_mode=overlay_mode):
            mode_text = "🛡️ 오버레이" if overlay_mode else "🎯"
            self.btn_pick.setText(f"{mode_text} 선택 중... (ESC 취소)")
            self.btn_pick.setEnabled(False)
            self.chk_overlay.setEnabled(False)
            
            msg = "🛡️ 오버레이 모드 - 요소와 상호작용 없이 선택" if overlay_mode else "🎯 브라우저에서 요소를 클릭하세요!"
            self.statusBar().showMessage(msg)
            
            self.picker_watcher = PickerWatcher(self.browser)
            self.picker_watcher.picked.connect(self._on_picked)
            self.picker_watcher.cancelled.connect(self._on_pick_cancelled)
            self.picker_watcher.start()
        else:
            self.statusBar().showMessage("요소 선택 모드를 시작할 수 없습니다")
    
    def _on_picked(self, result: Dict):
        """요소 선택됨"""
        self._reset_picker()
        
        # 편집기에 입력
        xpath = result.get('xpath', '')
        css = result.get('css', '')
        self.input_xpath.setPlainText(xpath)
        self.input_css.setText(css)
        
        if not self.input_name.text():
            el_id = result.get('id', '')
            if el_id:
                self.input_name.setText(el_id)
            else:
                self.input_name.setText(f"{result.get('tag', 'element')}_{datetime.now().strftime('%H%M%S')}")
        
        if not self.input_desc.text():
            text = result.get('text', '')[:40]
            self.input_desc.setText(text or f"{result.get('tag', '')} 요소")
        
        # 프레임 경로
        frame_path = result.get('frame_path', 'main')
        
        # 히스토리에 추가
        self._add_to_history(xpath, css, result.get('tag', ''), frame_path)
        
        # 결과 표시
        self.txt_result.setHtml(f"""
            <div style="color: #9b59b6; font-size: 14pt;">🎯 요소 선택됨!</div>
            <div style="margin-top: 10px;">
            <b>XPath:</b> <code>{result.get('xpath', '')[:60]}...</code><br>
            <b>CSS:</b> <code>{result.get('css', '')[:60]}...</code><br>
            <b>태그:</b> &lt;{result.get('tag', '')}&gt;<br>
            <b>ID:</b> {result.get('id', '-')}<br>
            <b>Class:</b> {result.get('className', '-')[:40]}<br>
            <b>텍스트:</b> {result.get('text', '-')[:50]}<br>
            <b>프레임:</b> <span style="color: #ffd166;">{frame_path}</span>
            </div>
        """)
        
        self._show_toast(f"요소 선택됨! (프레임: {frame_path})", "success")
    
    def _on_pick_cancelled(self):
        """선택 취소"""
        self._reset_picker()
        self.statusBar().showMessage("요소 선택이 취소되었습니다")
    
    def _reset_picker(self):
        """선택기 리셋"""
        self.btn_pick.setText("🎯 요소 선택 시작")
        self.btn_pick.setEnabled(True)
        self.chk_overlay.setEnabled(True)
        
        if self.picker_watcher:
            self.picker_watcher.stop()
            self.picker_watcher = None
    
    # ========== 검증 ==========
    
    def _validate_all(self):
        """전체 검증"""
        if not self.browser.is_alive():
            QMessageBox.warning(self, "알림", "브라우저가 연결되어 있지 않습니다.")
            return
        
        if not self.config.items:
            QMessageBox.warning(self, "알림", "검증할 항목이 없습니다.")
            return
        
        handles = [win['handle'] for win in self.browser.get_windows()]
        
        self.progress.setVisible(True)
        self.progress.setValue(0)
        
        self.validate_worker = ValidateWorker(self.browser, self.config.items, handles)
        self.validate_worker.progress.connect(self._on_validate_progress)
        self.validate_worker.validated.connect(self._on_validated)
        self.validate_worker.finished.connect(self._on_validate_finished)
        self.validate_worker.start()
    
    def _on_validate_progress(self, value: int, msg: str):
        """검증 진행"""
        self.progress.setValue(value)
        self.lbl_progress.setText(msg)
    
    def _on_validated(self, name: str, result: Dict):
        """항목 검증됨"""
        item = self.config.get_item(name)
        if item and result['found']:
            item.is_verified = True
            item.element_tag = result['tag']
            item.element_text = result['text']
            item.found_window = result.get('window', '')
            item.found_frame = result['frame']
    
    def _on_validate_finished(self, found: int, total: int):
        """검증 완료"""
        self.progress.setVisible(False)
        self.lbl_progress.clear()
        
        self._refresh_table(self.combo_filter.currentText())
        
        QMessageBox.information(
            self, "검증 완료",
            f"검증이 완료되었습니다.\n\n"
            f"✅ 발견: {found}개\n"
            f"⬜ 미발견: {total - found}개"
        )
    
    def _analyze_page(self):
        """페이지 분석"""
        if not self.browser.is_alive():
            return
        
        try:
            d = self.browser.driver
            info = {
                'buttons': len(d.find_elements(By.TAG_NAME, 'button')),
                'links': len(d.find_elements(By.TAG_NAME, 'a')),
                'inputs': len(d.find_elements(By.TAG_NAME, 'input')),
                'iframes': len(d.find_elements(By.TAG_NAME, 'iframe')),
                'forms': len(d.find_elements(By.TAG_NAME, 'form')),
            }
            
            QMessageBox.information(
                self, "페이지 분석",
                f"현재 페이지 요소 수:\n\n"
                f"🔘 버튼: {info['buttons']}개\n"
                f"🔗 링크: {info['links']}개\n"
                f"📝 입력: {info['inputs']}개\n"
                f"🖼️ iframe: {info['iframes']}개\n"
                f"📋 폼: {info['forms']}개"
            )
        except Exception as e:
            QMessageBox.warning(self, "오류", str(e))
    
    # ========== 파일 관리 ==========
    
    def _new_config(self):
        """새 설정"""
        reply = QMessageBox.question(
            self, "새 설정",
            "현재 설정을 초기화하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.config = SiteConfig.from_preset("빈 템플릿")
            self._refresh_table()
            self._clear_editor()
    
    def _open_config(self):
        """설정 열기"""
        filename, _ = QFileDialog.getOpenFileName(self, "설정 열기", "", "JSON (*.json)")
        
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    self.config = SiteConfig.from_dict(json.load(f))
                
                self.input_url.setText(self.config.url)
                self._refresh_table()
                self._clear_editor()
                self.statusBar().showMessage(f"📂 설정 로드: {filename}")
            except Exception as e:
                QMessageBox.critical(self, "오류", str(e))
    
    def _save_config(self):
        """설정 저장"""
        filename, _ = QFileDialog.getSaveFileName(
            self, "설정 저장",
            f"{self.config.name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.json",
            "JSON (*.json)"
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(self.config.to_dict(), f, ensure_ascii=False, indent=2)
                self.statusBar().showMessage(f"💾 저장됨: {filename}")
            except Exception as e:
                QMessageBox.critical(self, "오류", str(e))
    
    def _export(self, format_type: str):
        """내보내기"""
        ext_map = {'json': 'JSON (*.json)', 'dict': 'Python (*.py)', 'class': 'Python (*.py)', 'yaml': 'YAML (*.yaml)'}
        filename, _ = QFileDialog.getSaveFileName(
            self, "내보내기",
            f"xpath_config_{datetime.now().strftime('%Y%m%d')}.{format_type if format_type != 'dict' and format_type != 'class' else 'py'}",
            ext_map.get(format_type, '*.*')
        )
        
        if not filename:
            return
        
        try:
            if format_type == 'json':
                data = {item.name: {'xpath': item.xpath, 'css': item.css_selector, 'category': item.category, 'desc': item.description} for item in self.config.items}
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            
            elif format_type == 'dict':
                lines = [
                    '#!/usr/bin/env python3',
                    '# -*- coding: utf-8 -*-',
                    f'"""XPath 설정 - {self.config.name}"""',
                    '',
                    'XPATH = {'
                ]
                for item in self.config.items:
                    lines.append(f"    '{item.name}': '{item.xpath}',  # {item.description}")
                lines.append('}')
                
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(lines))
            
            elif format_type == 'class':
                lines = [
                    '#!/usr/bin/env python3',
                    '# -*- coding: utf-8 -*-',
                    f'"""XPath 설정 클래스 - {self.config.name}"""',
                    '',
                    'from dataclasses import dataclass',
                    '',
                    '@dataclass',
                    'class XPathConfig:',
                    f'    """XPath 설정 - {self.config.name}"""',
                    ''
                ]
                
                cats = {}
                for item in self.config.items:
                    if item.category not in cats:
                        cats[item.category] = []
                    cats[item.category].append(item)
                
                for cat, items in cats.items():
                    lines.append(f'    # === {cat.upper()} ===')
                    for item in items:
                        lines.append(f"    {item.name}: str = '{item.xpath}'")
                    lines.append('')
                
                lines.extend([
                    '    def get(self, name: str) -> str:',
                    '        return getattr(self, name, "")',
                    '',
                    '# 인스턴스',
                    'config = XPathConfig()',
                    ''
                ])
                
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(lines))
            
            elif format_type == 'yaml':
                lines = [f'# XPath 설정 - {self.config.name}', '', 'xpaths:']
                for item in self.config.items:
                    lines.extend([
                        f'  {item.name}:',
                        f'    xpath: "{item.xpath}"',
                        f'    category: "{item.category}"'
                    ])
                
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(lines))
            
            self.statusBar().showMessage(f"📤 내보내기 완료: {filename}")
            
        except Exception as e:
            QMessageBox.critical(self, "오류", str(e))
    
    def _load_settings(self):
        """설정 로드"""
        geo = self.settings.value("geometry")
        if geo:
            self.restoreGeometry(geo)
        
        # 폰트 크기 로드
        font_size = self.settings.value("font_size", 10, type=int)
        self._apply_font_size(font_size)
    
    # ========== 새로운 기능 메서드들 ==========
    
    def _show_toast(self, message: str, toast_type: str = "info"):
        """Toast 알림 표시 (statusbar 대신 사용)"""
        if hasattr(self, 'toast'):
            self.toast.show_toast(message, toast_type)
        self.statusBar().showMessage(message, 5000)  # 5초 동안 표시
    
    def _load_xpath_history(self):
        """XPath 히스토리 로드"""
        try:
            history_file = Path.home() / '.xpath_explorer' / 'xpath_history.json'
            if history_file.exists():
                with open(history_file, 'r', encoding='utf-8') as f:
                    self.xpath_history = json.load(f)
        except Exception as e:
            logger.warning(f"XPath 히스토리 로드 실패: {e}")
            self.xpath_history = []
    
    def _save_xpath_history(self):
        """XPath 히스토리 저장"""
        try:
            history_file = Path.home() / '.xpath_explorer' / 'xpath_history.json'
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(self.xpath_history[-self.max_history:], f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"XPath 히스토리 저장 실패: {e}")
    
    def _add_to_history(self, xpath: str, css: str = "", tag: str = "", frame: str = "main"):
        """XPath를 히스토리에 추가"""
        entry = {
            'xpath': xpath,
            'css': css,
            'tag': tag,
            'frame': frame,
            'timestamp': datetime.now().isoformat()
        }
        # 중복 제거
        self.xpath_history = [h for h in self.xpath_history if h.get('xpath') != xpath]
        self.xpath_history.append(entry)
        # 최대 개수 유지
        self.xpath_history = self.xpath_history[-self.max_history:]
    
    def _show_xpath_history(self):
        """XPath 히스토리 다이얼로그"""
        dialog = QDialog(self)
        dialog.setWindowTitle("📜 XPath 히스토리")
        dialog.setMinimumSize(700, 500)
        
        layout = QVBoxLayout(dialog)
        
        # 히스토리 테이블
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["XPath", "태그", "프레임", "시간"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setRowCount(len(self.xpath_history))
        
        for i, entry in enumerate(reversed(self.xpath_history)):
            table.setItem(i, 0, QTableWidgetItem(entry.get('xpath', '')[:80]))
            table.setItem(i, 1, QTableWidgetItem(entry.get('tag', '')))
            table.setItem(i, 2, QTableWidgetItem(entry.get('frame', 'main')))
            
            ts = entry.get('timestamp', '')
            try:
                dt = datetime.fromisoformat(ts)
                time_str = dt.strftime('%m/%d %H:%M')
            except:
                time_str = ts[:16] if ts else ''
            table.setItem(i, 3, QTableWidgetItem(time_str))
        
        layout.addWidget(table)
        
        # 버튼
        btn_layout = QHBoxLayout()
        
        btn_load = QPushButton("📋 선택 항목 사용")
        btn_load.clicked.connect(lambda: self._use_history_item(table, dialog))
        btn_layout.addWidget(btn_load)
        
        btn_clear = QPushButton("🗑️ 전체 삭제")
        btn_clear.clicked.connect(lambda: self._clear_history(dialog))
        btn_layout.addWidget(btn_clear)
        
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(dialog.close)
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)
        dialog.exec()
    
    def _use_history_item(self, table: QTableWidget, dialog: QDialog):
        """히스토리 항목 사용"""
        selected = table.selectedItems()
        if selected:
            row = selected[0].row()
            if row < len(self.xpath_history):
                entry = list(reversed(self.xpath_history))[row]
                self.input_xpath.setPlainText(entry.get('xpath', ''))
                self.input_css.setText(entry.get('css', ''))
                dialog.close()
                self._show_toast("히스토리에서 XPath 로드됨", "success")
    
    def _clear_history(self, dialog: QDialog):
        """히스토리 삭제"""
        self.xpath_history = []
        self._save_xpath_history()
        dialog.close()
        self._show_toast("히스토리가 삭제되었습니다", "info")
    
    # === 쿠키 관리 ===
    
    def _save_cookies(self):
        """현재 브라우저 쿠키 저장"""
        if not self.browser.is_alive():
            self._show_toast("브라우저가 연결되어 있지 않습니다", "warning")
            return
        
        try:
            cookies = self.browser.driver.get_cookies()
            domain = self.browser.driver.current_url.split('/')[2] if '/' in self.browser.driver.current_url else 'default'
            
            filename, _ = QFileDialog.getSaveFileName(
                self, "쿠키 저장",
                str(self.cookie_dir / f"{domain.replace('.', '_')}_cookies.json"),
                "JSON (*.json)"
            )
            
            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(cookies, f, ensure_ascii=False, indent=2)
                self._show_toast(f"쿠키 저장됨: {len(cookies)}개", "success")
                logger.info(f"쿠키 저장: {filename}")
        except Exception as e:
            logger.error(f"쿠키 저장 실패: {e}")
            self._show_toast(f"쿠키 저장 실패: {e}", "error")
    
    def _load_cookies(self):
        """저장된 쿠키 불러오기"""
        if not self.browser.is_alive():
            self._show_toast("브라우저가 연결되어 있지 않습니다", "warning")
            return
        
        filename, _ = QFileDialog.getOpenFileName(
            self, "쿠키 불러오기",
            str(self.cookie_dir),
            "JSON (*.json)"
        )
        
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    cookies = json.load(f)
                
                for cookie in cookies:
                    # 도메인 호환성을 위해 일부 필드 제거
                    for key in ['sameSite', 'storeId', 'id']:
                        cookie.pop(key, None)
                    try:
                        self.browser.driver.add_cookie(cookie)
                    except Exception as e:
                        logger.debug(f"쿠키 추가 실패: {cookie.get('name')}: {e}")
                
                self._show_toast(f"쿠키 로드됨: {len(cookies)}개 (페이지 새로고침 필요)", "success")
                logger.info(f"쿠키 로드: {filename}")
            except Exception as e:
                logger.error(f"쿠키 로드 실패: {e}")
                self._show_toast(f"쿠키 로드 실패: {e}", "error")
    
    def _clear_cookies(self):
        """현재 브라우저 쿠키 삭제"""
        if not self.browser.is_alive():
            self._show_toast("브라우저가 연결되어 있지 않습니다", "warning")
            return
        
        try:
            self.browser.driver.delete_all_cookies()
            self._show_toast("모든 쿠키가 삭제되었습니다", "success")
        except Exception as e:
            logger.error(f"쿠키 삭제 실패: {e}")
            self._show_toast(f"쿠키 삭제 실패: {e}", "error")
    
    # === 폰트 크기 조절 ===
    
    def _increase_font(self):
        """폰트 크기 증가"""
        current = self.settings.value("font_size", Config.FONT_SIZE_DEFAULT, type=int)
        new_size = min(current + 1, Config.FONT_SIZE_MAX)
        self._apply_font_size(new_size)
        self._show_toast(f"폰트 크기: {new_size}pt", "info")
    
    def _decrease_font(self):
        """폰트 크기 감소"""
        current = self.settings.value("font_size", Config.FONT_SIZE_DEFAULT, type=int)
        new_size = max(current - 1, Config.FONT_SIZE_MIN)
        self._apply_font_size(new_size)
        self._show_toast(f"폰트 크기: {new_size}pt", "info")
    
    def _reset_font(self):
        """폰트 크기 초기화"""
        self._apply_font_size(Config.FONT_SIZE_DEFAULT)
        self._show_toast("폰트 크기 초기화됨", "info")
    
    def _apply_font_size(self, size: int):
        """폰트 크기 적용"""
        self.settings.setValue("font_size", size)
        font = self.font()
        font.setPointSize(size)
        self.setFont(font)
    
    # === 도움말 ===
    
    def _show_shortcuts(self):
        """단축키 목록 다이얼로그"""
        shortcuts = """
        <h3>🎯 키보드 단축키</h3>
        <table style='margin: 10px; font-size: 11pt;'>
        <tr><td style='padding:5px;'><b>Ctrl+N</b></td><td>새 설정</td></tr>
        <tr><td style='padding:5px;'><b>Ctrl+O</b></td><td>설정 열기</td></tr>
        <tr><td style='padding:5px;'><b>Ctrl+S</b></td><td>설정 저장</td></tr>
        <tr><td style='padding:5px;'><b>F5</b></td><td>전체 검증</td></tr>
        <tr><td style='padding:5px;'><b>Ctrl++</b></td><td>폰트 크기 증가</td></tr>
        <tr><td style='padding:5px;'><b>Ctrl+-</b></td><td>폰트 크기 감소</td></tr>
        </table>
        
        <h3>🖱️ 요소 선택 모드</h3>
        <table style='margin: 10px; font-size: 11pt;'>
        <tr><td style='padding:5px;'><b>클릭</b></td><td>요소 선택 고정</td></tr>
        <tr><td style='padding:5px;'><b>더블클릭</b></td><td>XPath 복사 + 확정</td></tr>
        <tr><td style='padding:5px;'><b>Ctrl+C</b></td><td>현재 요소 XPath 복사</td></tr>
        <tr><td style='padding:5px;'><b>Enter</b></td><td>선택 확정 (고정 상태)</td></tr>
        <tr><td style='padding:5px;'><b>ESC</b></td><td>선택 취소/해제</td></tr>
        </table>
        """
        
        msg = QMessageBox(self)
        msg.setWindowTitle("단축키 목록")
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(shortcuts)
        msg.exec()
    
    def _show_about(self):
        """프로그램 정보"""
        about = f"""
        <h2>🎯 {Config.APP_NAME}</h2>
        <p><b>버전:</b> {Config.VERSION} (Refactored Edition)</p>
        <p><b>기능:</b></p>
        <ul>
        <li>실시간 요소 선택 및 XPath 추출</li>
        <li>다중 사이트 프리셋 지원</li>
        <li>중첩 iframe 탐색</li>
        <li>쿠키/세션 관리</li>
        <li>XPath 히스토리</li>
        <li>다양한 내보내기 형식</li>
        </ul>
        <p style='color: #778da9;'>
        Selenium + undetected_chromedriver 기반<br>
        PyQt6 UI
        </p>
        """
        
        msg = QMessageBox(self)
        msg.setWindowTitle("정보")
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(about)
        msg.exec()
    
    def closeEvent(self, event):
        """종료 - 스레드와 타이머 안전하게 정리"""
        logger.info("프로그램 종료 시작...")
        self.settings.setValue("geometry", self.saveGeometry())
        
        # XPath 히스토리 저장
        self._save_xpath_history()
        
        # 타이머 정지
        if hasattr(self, 'check_timer') and self.check_timer:
            self.check_timer.stop()
            logger.debug("브라우저 체크 타이머 정지")
        
        # 스레드 안전하게 종료
        if self.picker_watcher:
            self.picker_watcher.stop()
            self.picker_watcher.wait(Config.THREAD_TIMEOUT_MS)
            logger.debug("PickerWatcher 스레드 종료")
        
        if self.validate_worker:
            self.validate_worker.cancel()
            self.validate_worker.wait(Config.THREAD_TIMEOUT_MS)
            logger.debug("ValidateWorker 스레드 종료")
        
        self.browser.close()
        logger.info("프로그램 종료 완료")
        event.accept()


# ============================================================================
# 메인
# ============================================================================

def main():
    # HiDPI 스케일링 정책 설정
    from PyQt6.QtCore import Qt
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # DPI 스케일 정보 로깅
    screen = app.primaryScreen()
    if screen:
        dpi = screen.logicalDotsPerInch()
        scale = dpi / Config.BASE_DPI
        logger.info(f"화면 DPI: {dpi:.0f}, 스케일 비율: {scale:.2f}x")
    
    window = XPathExplorer()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
