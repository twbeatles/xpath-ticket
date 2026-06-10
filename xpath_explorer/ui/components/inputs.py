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

class NoWheelComboBox(QComboBox):
    """휠 스크롤로 값이 변경되지 않는 ComboBox"""

    def wheelEvent(self, e: Optional[QWheelEvent]):
        # 휠 이벤트 무시 (부모에게 전달)
        if e is not None:
            e.ignore()
class NoWheelSpinBox(QSpinBox):
    """휠 스크롤로 값이 변경되지 않는 SpinBox"""

    def wheelEvent(self, e: Optional[QWheelEvent]):
        if e is not None:
            e.ignore()
class NoWheelDoubleSpinBox(QDoubleSpinBox):
    """휠 스크롤로 값이 변경되지 않는 DoubleSpinBox"""

    def wheelEvent(self, e: Optional[QWheelEvent]):
        if e is not None:
            e.ignore()
class ModernSearchInput(QFrame):
    """
    모던 검색 입력창
    - 검색 아이콘 내장
    - 포커스 시 시각적 효과
    - 클리어 버튼
    """

    def __init__(self, placeholder: str = "검색...", parent=None):
        super().__init__(parent)
        self.setObjectName("modern_search")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 8, 0)
        layout.setSpacing(8)

        # 검색 아이콘
        self.lbl_icon = QLabel("🔍")
        self.lbl_icon.setStyleSheet("font-size: 14px; background: transparent; color: #6c7086;")
        layout.addWidget(self.lbl_icon)

        # 입력창
        self.input = QLineEdit()
        self.input.setPlaceholderText(placeholder)
        self.input.setStyleSheet("""
            QLineEdit {
                border: none;
                background: transparent;
                color: #cdd6f4;
                font-size: 14px;
                padding: 10px 0;
            }
        """)
        self.input.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.input, 1)

        # 클리어 버튼
        self.btn_clear = QPushButton("✕")
        self.btn_clear.setFixedSize(24, 24)
        self.btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear.setStyleSheet("""
            QPushButton {
                background: rgba(108, 112, 134, 0.3);
                border: none;
                border-radius: 12px;
                color: #a6adc8;
                font-size: 12px;
            }
            QPushButton:hover {
                background: rgba(243, 139, 168, 0.3);
                color: #f38ba8;
            }
        """)
        self.btn_clear.clicked.connect(self.clear)
        self.btn_clear.hide()
        layout.addWidget(self.btn_clear)

        # 프레임 스타일
        self._apply_base_style()

        # 포커스 이벤트
        self.input.installEventFilter(self)

    def _apply_base_style(self):
        self.setStyleSheet("""
            QFrame#modern_search {
                background: rgba(37, 37, 56, 0.95);
                border: 2px solid rgba(69, 71, 90, 0.7);
                border-radius: 12px;
            }
            QFrame#modern_search:hover {
                border: 2px solid rgba(137, 180, 250, 0.5);
            }
        """)

    def eventFilter(self, a0: QObject | None, a1: QEvent | None):
        obj = a0
        event = a1
        if event is None:
            return False
        if obj == self.input:
            if event.type() == QEvent.Type.FocusIn:
                self.setStyleSheet("""
                    QFrame#modern_search {
                        background: rgba(49, 50, 68, 1);
                        border: 2px solid #89b4fa;
                        border-radius: 12px;
                    }
                """)
            elif event.type() == QEvent.Type.FocusOut:
                self._apply_base_style()
        return super().eventFilter(obj, event)

    def _on_text_changed(self, text):
        self.btn_clear.setVisible(bool(text))

    def text(self) -> str:
        return self.input.text()

    def setText(self, text: str):
        self.input.setText(text)

    def clear(self):
        self.input.clear()

    def setPlaceholderText(self, text: str):
        self.input.setPlaceholderText(text)
