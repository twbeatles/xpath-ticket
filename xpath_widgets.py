# -*- coding: utf-8 -*-
"""
XPath Explorer Widgets v3.4
- Enhanced Toast notifications with slide animation
- Modern styling and effects
- NoWheel widgets for better UX
"""

from PyQt6.QtWidgets import (
    QLabel, QFrame, QHBoxLayout, QPushButton, QGraphicsOpacityEffect, 
    QGraphicsDropShadowEffect, QComboBox, QSpinBox, QDoubleSpinBox
)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint, QEvent
from PyQt6.QtGui import QColor


class NoWheelComboBox(QComboBox):
    """휠 스크롤로 값이 변경되지 않는 ComboBox"""
    
    def wheelEvent(self, event):
        # 휠 이벤트 무시 (부모에게 전달)
        event.ignore()


class NoWheelSpinBox(QSpinBox):
    """휠 스크롤로 값이 변경되지 않는 SpinBox"""
    
    def wheelEvent(self, event):
        event.ignore()


class NoWheelDoubleSpinBox(QDoubleSpinBox):
    """휠 스크롤로 값이 변경되지 않는 DoubleSpinBox"""
    
    def wheelEvent(self, event):
        event.ignore()



class ToastWidget(QFrame):
    """
    화면 상단에 표시되는 모던 Toast 알림
    - 슬라이드 + 페이드 애니메이션
    - 테마 색상 지원
    - 그림자 효과
    """
    
    # 테마별 색상 정의 (bg, accent, icon, glow)
    THEMES = {
        "success": {
            "bg": "rgba(30, 60, 40, 0.95)",
            "accent": "#a6e3a1",
            "icon": "✅",
            "glow": "rgba(166, 227, 161, 0.4)"
        },
        "warning": {
            "bg": "rgba(60, 45, 30, 0.95)",
            "accent": "#fab387",
            "icon": "⚠️",
            "glow": "rgba(250, 179, 135, 0.4)"
        },
        "error": {
            "bg": "rgba(60, 30, 35, 0.95)",
            "accent": "#f38ba8",
            "icon": "❌",
            "glow": "rgba(243, 139, 168, 0.4)"
        },
        "info": {
            "bg": "rgba(30, 40, 60, 0.95)",
            "accent": "#89b4fa",
            "icon": "ℹ️",
            "glow": "rgba(137, 180, 250, 0.4)"
        }
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("toast_widget")
        
        # 레이아웃 설정
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)
        
        # 아이콘 라벨
        self.lbl_icon = QLabel()
        self.lbl_icon.setStyleSheet("font-size: 18px; background: transparent;")
        self.lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_icon.setMinimumWidth(24)
        layout.addWidget(self.lbl_icon)
        
        # 메시지 라벨
        self.label = QLabel()
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.label, 1)
        
        # 닫기 버튼
        self.btn_close = QPushButton("✕")
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.setFixedSize(24, 24)
        self.btn_close.clicked.connect(self._close_toast)
        layout.addWidget(self.btn_close)
        
        # 초기 숨김
        self.hide()
        
        # 타이머
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._start_fade_out)
        
        # 애니메이션 객체 (재사용을 위해 None 초기화)
        self._fade_anim = None
        self._slide_anim = None
        self._fade_out_anim = None
        self._slide_up_anim = None
        
        # 그래픽 효과 객체
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(1.0)
        
        # 그림자 효과
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(30)
        self._shadow.setColor(QColor(0, 0, 0, 120))
        self._shadow.setOffset(0, 8)
        
    def show_toast(self, message: str, toast_type: str = "info", duration: int = 3000):
        """
        Toast 메시지 표시
        
        Args:
            message: 표시할 메시지
            toast_type: "success", "warning", "error", "info"
            duration: 표시 시간 (ms), 0이면 자동 닫힘 없음
        """
        # 이전 타이머 정지
        self._timer.stop()
        
        # 테마 가져오기
        theme = self.THEMES.get(toast_type, self.THEMES["info"])
        
        # 동적 스타일 적용
        self.setStyleSheet(f"""
            QFrame#toast_widget {{
                background: {theme['bg']};
                border-radius: 14px;
                border: 2px solid {theme['accent']};
            }}
            QLabel {{
                color: #ffffff;
                font-family: 'Pretendard', 'Segoe UI', sans-serif;
                font-weight: 600;
                font-size: 14px;
                background: transparent;
            }}
            QPushButton {{
                background: transparent;
                border: none;
                color: rgba(255, 255, 255, 0.5);
                font-weight: bold;
                font-size: 14px;
                border-radius: 12px;
            }}
            QPushButton:hover {{
                color: #ffffff;
                background: rgba(255, 255, 255, 0.15);
            }}
        """)
        
        # 그림자 색상 업데이트
        self._shadow.setColor(QColor(theme['glow']))
        self.setGraphicsEffect(self._shadow)
        
        # 컨텐츠 설정
        self.lbl_icon.setText(theme['icon'])
        self.label.setText(message)
        
        # 크기 조정
        self.adjustSize()
        self.setMinimumWidth(300)
        self.setMaximumWidth(600)
        
        # 위치 설정 (중앙 상단)
        self._update_position()
        
        # 애니메이션 시작
        self._start_slide_in()
        
        # 자동 닫기 타이머
        if duration > 0:
            self._timer.start(duration)
    
    def _update_position(self):
        """Toast 위치 업데이트 (부모 중앙 상단)"""
        if self.parent():
            parent_rect = self.parent().rect()
            x = (parent_rect.width() - self.width()) // 2
            self._target_y = 40  # 최종 위치
            self._start_y = -self.height() - 20  # 시작 위치 (화면 밖)
            self.move(x, self._start_y)
    
    def _start_slide_in(self):
        """슬라이드 인 + 페이드 인 애니메이션"""
        self.show()
        self.raise_()
        
        # 기존 애니메이션 정리 (메모리 누수 방지)
        self._cleanup_animations()
        
        # 투명도 효과 설정
        self.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(0)
        
        # 페이드 인
        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._fade_anim.setDuration(300)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_anim.start()
        
        # 슬라이드 다운 (위치 애니메이션)
        self._slide_anim = QPropertyAnimation(self, b"pos", self)
        self._slide_anim.setDuration(350)
        self._slide_anim.setStartValue(QPoint(self.x(), self._start_y))
        self._slide_anim.setEndValue(QPoint(self.x(), self._target_y))
        self._slide_anim.setEasingCurve(QEasingCurve.Type.OutBack)
        self._slide_anim.finished.connect(self._on_slide_in_finished)
        self._slide_anim.start()
    
    def _on_slide_in_finished(self):
        """슬라이드 인 완료 후 그림자 효과 적용"""
        # 그림자 다시 적용 (opacity effect와 충돌 방지)
        self._shadow.setBlurRadius(25)
        self.setGraphicsEffect(self._shadow)
    
    def _start_fade_out(self):
        """페이드 아웃 + 슬라이드 업 애니메이션"""
        # 기존 애니메이션 정리
        self._cleanup_animations()
        
        # 투명도 효과로 전환
        self.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(1.0)
        
        # 페이드 아웃
        self._fade_out_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._fade_out_anim.setDuration(250)
        self._fade_out_anim.setStartValue(1.0)
        self._fade_out_anim.setEndValue(0.0)
        self._fade_out_anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self._fade_out_anim.finished.connect(self.hide)
        self._fade_out_anim.start()
        
        # 슬라이드 업
        self._slide_up_anim = QPropertyAnimation(self, b"pos", self)
        self._slide_up_anim.setDuration(250)
        self._slide_up_anim.setStartValue(QPoint(self.x(), self.y()))
        self._slide_up_anim.setEndValue(QPoint(self.x(), self._start_y))
        self._slide_up_anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self._slide_up_anim.start()
    
    def _cleanup_animations(self):
        """기존 애니메이션 정리 (메모리 누수 방지)"""
        for anim in [self._fade_anim, self._slide_anim, 
                     self._fade_out_anim, self._slide_up_anim]:
            if anim is not None:
                anim.stop()
                anim.deleteLater()
        
        self._fade_anim = None
        self._slide_anim = None
        self._fade_out_anim = None
        self._slide_up_anim = None
    
    def _close_toast(self):
        """Toast 즉시 닫기"""
        self._timer.stop()
        self._start_fade_out()


class StatusIndicator(QFrame):
    """
    연결 상태 표시 인디케이터
    - 애니메이션 glow 효과
    - 상태별 색상
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(12, 12)
        self._connected = False
        self._update_style()
    
    def set_connected(self, connected: bool):
        """연결 상태 설정"""
        self._connected = connected
        self._update_style()
    
    def _update_style(self):
        """스타일 업데이트"""
        if self._connected:
            color = "#a6e3a1"
            glow = "rgba(166, 227, 161, 0.6)"
        else:
            color = "#f38ba8"
            glow = "rgba(243, 139, 168, 0.6)"
        
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {color};
                border-radius: 6px;
                border: 2px solid {glow};
            }}
        """)


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
