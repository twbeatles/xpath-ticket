# -*- coding: utf-8 -*-
# pyright: reportAttributeAccessIssue=false, reportCallIssue=false, reportArgumentType=false
"""XPath Explorer mixin module (auto-split from legacy main file)."""


from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QSplitter
)
from PySide6.QtCore import Qt

from xpath_explorer.core.constants import (
    APP_TITLE,
)
from xpath_explorer.ui.styles import STYLE
from xpath_explorer.ui.widgets import ToastWidget



class ExplorerUIWindowMixin:
    def _init_ui(self):
        """UI 초기화"""
        self.setWindowTitle(APP_TITLE)
        self.resize(1400, 900)
        
        # 중앙 위젯
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 메인 레이아웃
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # 1. 메뉴바
        self._create_menu()
        
        # 2. 브라우저 컨트롤 패널
        self._create_browser_panel()
        main_layout.addLayout(self.browser_layout)
        
        # 2.5 URL 패널 (Collapsible)
        self.url_panel = self._create_url_panel()
        main_layout.addWidget(self.url_panel)

        
        # 3. 메인 작업 영역 (스플리터)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self.splitter, 1)
        
        # 3.1 왼쪽: XPath 목록
        self.left_panel = QWidget()
        self._create_list_panel()
        self.splitter.addWidget(self.left_panel)
        
        # 3.2 오른쪽: 상세 편집 및 도구
        self.right_panel = QWidget()
        self._create_editor_panel()
        self.splitter.addWidget(self.right_panel)
        
        # 스플리터 비율 (6:4)
        self.splitter.setStretchFactor(0, 6)
        self.splitter.setStretchFactor(1, 4)
        
        # 4. 상태 표시줄 패널
        self._create_status_panel()
        main_layout.addLayout(self.status_layout)
        
        # 스타일 적용
        self.setStyleSheet(STYLE)
        
        # Toast 알림 초기화
        self.toast = ToastWidget(self)

    def resizeEvent(self, a0):
        """[BUG-002] 윈도우 리사이즈 시 Toast 위치 업데이트"""
        super().resizeEvent(a0)
        if hasattr(self, 'toast') and self.toast.isVisible():
            self.toast._update_position()
