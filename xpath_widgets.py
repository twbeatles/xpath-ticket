# -*- coding: utf-8 -*-
"""
XPath Explorer Widgets
"""

from PyQt6.QtWidgets import QLabel, QFrame, QHBoxLayout, QPushButton, QSizePolicy, QGraphicsOpacityEffect, QGraphicsDropShadowEffect
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor

class ToastWidget(QFrame):
    """화면 상단에 표시되는 toast 알림 (애니메이션 포함)"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        # 기본 스타일 (테마 색상 적용)
        self.setStyleSheet("""
            QFrame {
                background-color: #313244;
                border-radius: 12px;
                border: 1px solid #45475a;
            }
            QLabel {
                color: #cdd6f4;
                font-weight: 600;
                padding: 12px 20px;
                background: transparent;
                font-family: 'Pretendard', 'Malgun Gothic', sans-serif;
            }
            QPushButton {
                background: transparent;
                border: none;
                color: #9399b2;
                font-weight: bold;
                font-size: 14px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                color: #cdd6f4;
                background: rgba(255, 255, 255, 0.1);
                border-radius: 6px;
            }
        """)
        
        layout = QHBoxLayout()
        layout.setContentsMargins(8, 0, 8, 0)
        
        # 아이콘 라벨
        self.lbl_icon = QLabel()
        self.lbl_icon.setStyleSheet("font-size: 16px; padding-right: 5px;")
        layout.addWidget(self.lbl_icon)
        
        # 메시지 라벨
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)
        
        # 닫기 버튼
        self.btn_close = QPushButton("✕")
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.clicked.connect(self._close_toast)
        layout.addWidget(self.btn_close)
        
        self.setLayout(layout)
        
        # 그림자 효과 강화
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 100))
        shadow.setOffset(0, 10)
        self.setGraphicsEffect(shadow)
        
        self.hide()
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._start_fade_out)
        
        # 투명도 효과 (애니메이션용)
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        
    def show_toast(self, message: str, toast_type: str = "info", duration: int = 3000):
        """
        Toast 메시지 표시 (페이드 인 애니메이션)
        
        Args:
            message: 표시할 메시지
            toast_type: "success", "warning", "error", "info"
            duration: 표시 시간 (ms), 0이면 자동 닫힘 없음
        """
        # 테마 색상 (Catppuccin Style)
        # Success: Green (#a6e3a1), Warning: Peach (#fab387), Error: Red (#f38ba8), Info: Blue (#89b4fa)
        # 배경색은 약간 어둡게 처리하여 가독성 확보
        colors = {
            "success": ("#1e3626", "#a6e3a1", "✅"),  # Dark Green BG, Green Border/Text
            "warning": ("#3d2a1e", "#fab387", "⚠️"),  # Dark Orange BG
            "error":   ("#361e24", "#f38ba8", "❌"),  # Dark Red BG
            "info":    ("#1e2536", "#89b4fa", "ℹ️")   # Dark Blue BG
        }
        
        bg_color, accent_color, icon = colors.get(toast_type, colors["info"])
        
        # 동적 스타일 적용
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border-radius: 12px;
                border: 2px solid {accent_color};
            }}
            QLabel {{
                color: #ffffff;
                font-weight: 600;
                padding: 10px;
                background: transparent;
            }}
            QPushButton {{
                background: transparent;
                border: none;
                color: rgba(255, 255, 255, 0.6);
                font-weight: bold;
                font-size: 14px;
                padding: 5px 10px;
            }}
            QPushButton:hover {{
                color: #ffffff;
                background: rgba(255, 255, 255, 0.15);
                border-radius: 6px;
            }}
        """)
        
        self.lbl_icon.setText(icon)
        self.label.setText(message)
        self.adjustSize()
        
        # 부모 위젯 중앙 상단에 배치
        self._update_position()
        
        # 표시 및 페이드 인
        self._opacity_effect.setOpacity(0)
        self.show()
        self.raise_()
        
        self._fade_in_anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_in_anim.setDuration(250)
        self._fade_in_anim.setStartValue(0.0)
        self._fade_in_anim.setEndValue(1.0)
        self._fade_in_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_in_anim.start()
        
        if duration > 0:
            self._timer.start(duration)
    
    def _update_position(self):
        """Toast 위치 업데이트"""
        if self.parent():
            parent_rect = self.parent().rect()
            x = (parent_rect.width() - self.width()) // 2
            self.move(x, 50) # 상단 여백
    
    def _start_fade_out(self):
        """페이드 아웃 시작"""
        self._fade_out_anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_out_anim.setDuration(300)
        self._fade_out_anim.setStartValue(1.0)
        self._fade_out_anim.setEndValue(0.0)
        self._fade_out_anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self._fade_out_anim.finished.connect(self.hide)
        self._fade_out_anim.start()
    
    def _close_toast(self):
        """Toast 즉시 닫기"""
        self._timer.stop()
        self._start_fade_out()
