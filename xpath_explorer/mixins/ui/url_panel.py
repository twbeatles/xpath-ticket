# -*- coding: utf-8 -*-
# pyright: reportAttributeAccessIssue=false, reportCallIssue=false, reportArgumentType=false
"""XPath Explorer mixin module (auto-split from legacy main file)."""


from PySide6.QtWidgets import (
    QWidget, QHBoxLayout,
    QPushButton, QLineEdit
)
from PySide6.QtCore import Qt

from xpath_explorer.ui.widgets import CollapsibleBox



class ExplorerUIUrlPanelMixin:
    def _create_url_panel(self):
        """URL 입력 패널 (Collapsible)"""
        # 컨텐츠 위젯
        content = QWidget()
        layout = QHBoxLayout(content)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # 큰 URL 입력창
        self.input_url = QLineEdit()
        self.input_url.setObjectName("url_input_large")
        self.input_url.setPlaceholderText("https://...")
        self.input_url.returnPressed.connect(self._navigate)
        layout.addWidget(self.input_url, 1)
        
        # 큰 이동 버튼
        self.btn_go = QPushButton("이동")
        self.btn_go.setObjectName("primary")
        self.btn_go.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_go.setFixedSize(80, 42)
        self.btn_go.setStyleSheet("font-size: 15px; font-weight: bold;")
        self.btn_go.clicked.connect(self._navigate)
        layout.addWidget(self.btn_go)
        
        # 접이식 박스 생성
        self.url_collapsible = CollapsibleBox("🌐 URL 주소창", expanded=True)
        self.url_collapsible.setContentLayout(layout)
        
        return self.url_collapsible
