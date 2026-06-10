# -*- coding: utf-8 -*-
"""
XPath Explorer Widgets v3.6
- Enhanced Toast notifications with slide animation
- Modern styling and effects
- NoWheel widgets for better UX
- AnimatedStatusIndicator with pulse effect
- ModernSearchInput with focus animation
"""

from PyQt6.QtWidgets import (
    QLabel, QFrame, QHBoxLayout, QVBoxLayout, QPushButton, QGraphicsOpacityEffect,
    QGraphicsDropShadowEffect, QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit,
    QWidget, QSizePolicy, QToolButton
)
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint, QEvent, QObject, pyqtSignal
from PyQt6.QtGui import QColor, QWheelEvent

class CollapsibleBox(QWidget):
    """
    접이식 박스 위젯
    - 부드러운 애니메이션
    - 커스텀 헤더 (화살표 + 제목)
    """

    toggled = pyqtSignal(bool)

    def __init__(self, title="", parent=None, expanded=True):
        super().__init__(parent)

        self._expanded = expanded

        # 메인 레이아웃
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 헤더/토글 버튼
        self.toggle_button = QToolButton()
        self.toggle_button.setText(title)
        self.toggle_button.setStyleSheet("""
            QToolButton {
                border: none;
                color: #cdd6f4;
                background-color: transparent;
                font-weight: bold;
                padding: 1px;
                font-size: 13px;
            }
            QToolButton:hover {
                color: #89b4fa;
            }
        """)
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle_button.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(expanded)
        self.toggle_button.clicked.connect(self._on_toggle)

        # 헤더 컨테이너 (옵션: 별도의 헤더 영역이 필요한 경우 사용)
        # 현재는 버튼 자체가 헤더 역할

        self.main_layout.addWidget(self.toggle_button)

        # 컨텐츠 영역
        self.content_area = QWidget()
        self.content_area.setMaximumHeight(16777215 if expanded else 0)
        self.content_area.setMinimumHeight(0)
        self.content_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        # 애니메이션
        self.animation = QPropertyAnimation(self.content_area, b"maximumHeight")
        self.animation.setDuration(300)
        self.animation.setEasingCurve(QEasingCurve.Type.OutQuart)

        self.main_layout.addWidget(self.content_area)

    def setContentLayout(self, layout):
        """컨텐츠 영역 레이아웃 설정"""
        self.content_area.setLayout(layout)

    def _on_toggle(self, checked):
        self.toggle(checked)

    def toggle(self, expanded):
        self._expanded = expanded

        # 화살표 변경
        self.toggle_button.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)

        # 애니메이션 시작
        # 현재 컨텐츠의 높이 계산
        content_layout = self.content_area.layout()
        if content_layout is None:
            self.toggled.emit(expanded)
            return
        content_layout.activate()
        content_height = content_layout.sizeHint().height()

        self.animation.stop()
        if expanded:
            self.animation.setStartValue(0)
            self.animation.setEndValue(content_height)
        else:
            self.animation.setStartValue(content_height)
            self.animation.setEndValue(0)

        self.animation.start()

        self.toggled.emit(expanded)

    def set_title(self, title):
        self.toggle_button.setText(title)
