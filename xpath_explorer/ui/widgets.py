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

    def _ensure_shadow_effect(self) -> QGraphicsDropShadowEffect:
        """Qt가 기존 effect를 삭제한 경우 안전하게 재생성한다."""
        shadow = getattr(self, "_shadow", None)
        if shadow is not None:
            try:
                shadow.blurRadius()
                return shadow
            except RuntimeError:
                pass

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 120))
        shadow.setOffset(0, 8)
        self._shadow = shadow
        return shadow

    def _ensure_opacity_effect(self) -> QGraphicsOpacityEffect:
        """Qt가 기존 effect를 삭제한 경우 안전하게 재생성한다."""
        opacity_effect = getattr(self, "_opacity_effect", None)
        if opacity_effect is not None:
            try:
                opacity_effect.opacity()
                return opacity_effect
            except RuntimeError:
                pass

        opacity_effect = QGraphicsOpacityEffect(self)
        opacity_effect.setOpacity(1.0)
        self._opacity_effect = opacity_effect
        return opacity_effect
        
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
        
        # 진행 중인 애니메이션 즉시 정리 (중복 방지)
        self._cleanup_animations()
        
        # 위젯이 보이는 상태면 즉시 숨김 후 재표시
        if self.isVisible():
            self.hide()
        
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
        shadow = self._ensure_shadow_effect()
        shadow.setColor(QColor(theme['glow']))
        self.setGraphicsEffect(shadow)
        
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
        parent = self.parentWidget()
        if parent is None:
            return
        parent_rect = parent.rect()
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
        opacity_effect = self._ensure_opacity_effect()
        self.setGraphicsEffect(opacity_effect)
        opacity_effect.setOpacity(0)
        
        # 페이드 인
        self._fade_anim = QPropertyAnimation(opacity_effect, b"opacity", self)
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
        shadow = self._ensure_shadow_effect()
        shadow.setBlurRadius(25)
        self.setGraphicsEffect(shadow)
    
    def _start_fade_out(self):
        """페이드 아웃 + 슬라이드 업 애니메이션"""
        # 기존 애니메이션 정리
        self._cleanup_animations()
        
        # 투명도 효과로 전환
        opacity_effect = self._ensure_opacity_effect()
        self.setGraphicsEffect(opacity_effect)
        opacity_effect.setOpacity(1.0)
        
        # 페이드 아웃
        self._fade_out_anim = QPropertyAnimation(opacity_effect, b"opacity", self)
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


class AnimatedStatusIndicator(QFrame):
    """
    펄스 애니메이션이 있는 상태 인디케이터
    - 연결/해제 상태에 따른 색상 변경
    - 부드러운 펄스 효과
    - 위젯 삭제 시 타이머 안전 정리
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(16, 16)
        self._connected = False
        self._pulse_opacity = 1.0
        
        # 펄스 애니메이션
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._do_pulse)
        self._pulse_direction = -1
        
        self._update_style()
    
    def set_connected(self, connected: bool):
        """연결 상태 설정"""
        if self._connected == connected:
            return
            
        self._connected = connected
        self._update_style()
        
        # 연결 시 펄스 애니메이션 시작
        if connected:
            self._pulse_timer.start(50)
        else:
            self._pulse_timer.stop()
            self._pulse_opacity = 1.0
    
    def is_connected(self) -> bool:
        return self._connected
    
    def _do_pulse(self):
        """펄스 애니메이션 프레임"""
        self._pulse_opacity += self._pulse_direction * 0.03
        
        if self._pulse_opacity <= 0.4:
            self._pulse_direction = 1
        elif self._pulse_opacity >= 1.0:
            self._pulse_direction = -1
            
        self._update_style()
    
    def _update_style(self):
        """스타일 업데이트"""
        if self._connected:
            color = "#a6e3a1"
            glow_base = (166, 227, 161)
        else:
            color = "#f38ba8"
            glow_base = (243, 139, 168)
        
        glow = f"rgba({glow_base[0]}, {glow_base[1]}, {glow_base[2]}, {self._pulse_opacity * 0.6:.2f})"
        
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {color};
                border-radius: 8px;
                border: 2px solid {glow};
            }}
        """)
    
    def cleanup(self):
        """리소스 정리 (명시적 호출용)"""
        if self._pulse_timer.isActive():
            self._pulse_timer.stop()
    
    def deleteLater(self):
        """위젯 삭제 시 타이머 안전 정리"""
        self.cleanup()
        super().deleteLater()


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


class EmptyStateWidget(QFrame):
    """
    빈 상태를 표시하는 위젯
    - 아이콘 + 메시지 + 액션 버튼
    """
    
    def __init__(
        self,
        icon: str = "📭",
        message: str = "데이터가 없습니다.",
        action_text: str | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("empty_state_widget")
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(16)
        
        # 아이콘
        self.lbl_icon = QLabel(icon)
        self.lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_icon.setStyleSheet("font-size: 48px; background: transparent;")
        layout.addWidget(self.lbl_icon)
        
        # 메시지
        self.lbl_message = QLabel(message)
        self.lbl_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_message.setWordWrap(True)
        self.lbl_message.setStyleSheet("""
            color: #7f849c;
            font-size: 15px;
            font-weight: 600;
            background: transparent;
        """)
        layout.addWidget(self.lbl_message)
        
        # 액션 버튼 (옵션)
        self.btn_action = None
        if action_text:
            self.btn_action = QPushButton(action_text)
            self.btn_action.setObjectName("primary")
            self.btn_action.setCursor(Qt.CursorShape.PointingHandCursor)
            layout.addWidget(self.btn_action, 0, Qt.AlignmentFlag.AlignCenter)
        
        self.setStyleSheet("""
            QFrame#empty_state_widget {
                background: transparent;
                padding: 40px;
            }
        """)
    
    def set_icon(self, icon: str):
        self.lbl_icon.setText(icon)
    
    def set_message(self, message: str):
        self.lbl_message.setText(message)


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
