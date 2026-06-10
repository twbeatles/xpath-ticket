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

class GradientButton(QPushButton):
    """
    그라데이션 배경을 가진 커스텀 버튼
    - 호버 시 색상 변화
    - 누름 시 피드백
    """

    PRESETS = {
        "blue": ("#89b4fa", "#74c7ec"),
        "purple": ("#cba6f7", "#f5c2e7"),
        "green": ("#a6e3a1", "#94e2d5"),
        "red": ("#f38ba8", "#eba0ac"),
        "orange": ("#fab387", "#f9e2af"),
    }

    def __init__(self, text: str = "", preset: str = "blue", parent=None):
        super().__init__(text, parent)
        self._preset = preset
        self._colors = self.PRESETS.get(preset, self.PRESETS["blue"])
        self._apply_style()
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _apply_style(self):
        c1, c2 = self._colors
        self.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                            stop:0 {c1}, stop:1 {c2});
                color: #1e1e2e;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: 700;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                            stop:0 {c2}, stop:1 {c1});
            }}
            QPushButton:pressed {{
                background: {c1};
            }}
        """)
class IconButton(QPushButton):
    """
    아이콘 버튼 (호버 효과 강화)
    """

    def __init__(self, icon: str = "", size: int = 28, parent=None):
        super().__init__(icon, parent)
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._size = size
        self._apply_style()

    def _apply_style(self):
        self.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid transparent;
                border-radius: {self._size // 2}px;
                font-size: {self._size // 2 + 2}px;
                color: #a6adc8;
            }}
            QPushButton:hover {{
                background: rgba(137, 180, 250, 0.2);
                border: 1px solid rgba(137, 180, 250, 0.4);
                color: #89b4fa;
            }}
            QPushButton:pressed {{
                background: rgba(137, 180, 250, 0.35);
            }}
        """)
