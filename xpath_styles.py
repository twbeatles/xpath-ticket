# -*- coding: utf-8 -*-
"""
XPath Explorer Stylesheet (Modern Dark Theme)
"""

STYLE = """
* {
    font-family: 'Pretendard', 'Malgun Gothic', 'Segoe UI', sans-serif;
    font-size: 14px;
}

QMainWindow {
    background-color: #1e1e2e;
}

QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
}

/* 탭 위젯 */
QTabWidget::pane {
    border: 1px solid #313244;
    background: #1e1e2e;
    border-radius: 8px;
}

QTabBar::tab {
    background: #181825;
    color: #a6adc8;
    padding: 12px 24px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    margin-right: 4px;
    font-weight: 600;
}

QTabBar::tab:selected {
    background: #313244;
    color: #ffffff;
    border-bottom: 2px solid #89b4fa;
}

QTabBar::tab:hover {
    background: #313244;
    color: #ffffff;
}

/* 그룹박스 */
QGroupBox {
    border: 1px solid #45475a;
    border-radius: 8px;
    margin-top: 28px;
    padding-top: 18px;
    background-color: #252538;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top center;
    padding: 6px 12px;
    background-color: #1e1e2e;
    border: 1px solid #45475a;
    border-radius: 12px;
    color: #89b4fa;
    font-weight: bold;
}

/* 입력 필드 */
QLineEdit, QPlainTextEdit, QTextEdit {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 10px;
    color: #cdd6f4;
    selection-background-color: #89b4fa;
    selection-color: #1e1e2e;
}

QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {
    border: 1px solid #89b4fa;
    background-color: #313244;
}

QLineEdit:hover, QPlainTextEdit:hover, QTextEdit:hover {
    border: 1px solid #585b70;
}

/* 기본 버튼 */
QPushButton {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 8px 16px;
    color: #cdd6f4;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #45475a;
    border: 1px solid #585b70;
}

QPushButton:pressed {
    background-color: #1e1e2e;
}

QPushButton:disabled {
    background-color: #181825;
    color: #585b70;
    border: 1px solid #313244;
}

/* 주요 버튼 (Primary) - Blue */
QPushButton#primary {
    background-color: #89b4fa;
    color: #1e1e2e;
    border: none;
}
QPushButton#primary:hover {
    background-color: #b4befe;
}
QPushButton#primary:pressed {
    background-color: #74c7ec;
}

/* 성공 버튼 (Success) - Green */
QPushButton#success {
    background-color: #a6e3a1;
    color: #1e1e2e;
    border: none;
}
QPushButton#success:hover {
    background-color: #94e2d5;
}

/* 위험 버튼 (Danger) - Red */
QPushButton#danger {
    background-color: #f38ba8;
    color: #1e1e2e;
    border: none;
}
QPushButton#danger:hover {
    background-color: #eba0ac;
}

/* 경고 버튼 (Warning) - Orange/Yellow */
QPushButton#warning {
    background-color: #fab387;
    color: #1e1e2e;
    border: none;
}
QPushButton#warning:hover {
    background-color: #f9e2af;
}

/* 요소 선택 피커 버튼 - Large Purple */
QPushButton#picker {
    background-color: #cba6f7;
    color: #1e1e2e;
    font-size: 15pt;
    padding: 20px 30px;
    border-radius: 12px;
    border: none;
}
QPushButton#picker:hover {
    background-color: #f5c2e7;
}

/* 아이콘 버튼 */
QPushButton#icon_btn {
    background-color: transparent;
    border: none;
    padding: 6px;
}
QPushButton#icon_btn:hover {
    background-color: #45475a;
    border-radius: 4px;
}

/* 콤보박스 */
QComboBox {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 8px 12px;
    color: #cdd6f4;
    min-width: 8em;
}

QComboBox:hover {
    border: 1px solid #89b4fa;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 5px solid #a6adc8;
    margin-right: 8px;
}

QComboBox QAbstractItemView {
    background-color: #313244;
    border: 1px solid #45475a;
    color: #cdd6f4;
    selection-background-color: #585b70;
}

/* 테이블 위젯 */
QTableWidget {
    background-color: #1e1e2e;
    alternate-background-color: #252538;
    gridline-color: #313244;
    border: 1px solid #45475a;
    border-radius: 6px;
}

QTableWidget::item {
    padding: 8px;
    border-bottom: 1px solid #313244;
}

QTableWidget::item:selected {
    background-color: #45475a;
    color: #ffffff;
}

QHeaderView::section {
    background-color: #181825;
    padding: 10px;
    border: none;
    border-bottom: 2px solid #45475a;
    color: #a6adc8;
    font-weight: bold;
}

/* 스크롤바 (슬림하고 모던하게) */
QScrollBar:vertical {
    border: none;
    background: #1e1e2e;
    width: 8px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #45475a;
    min-height: 30px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #585b70;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    border: none;
    background: #1e1e2e;
    height: 8px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: #45475a;
    min-width: 30px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal:hover {
    background: #585b70;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* 메뉴바 */
QMenuBar {
    background-color: #181825;
    color: #cdd6f4;
    border-bottom: 1px solid #313244;
}
QMenuBar::item {
    padding: 8px 12px;
    background: transparent;
}
QMenuBar::item:selected {
    background: #313244;
}

QMenu {
    background-color: #1e1e2e;
    color: #cdd6f4;
    border: 1px solid #45475a;
    padding: 5px;
}
QMenu::item {
    padding: 6px 24px;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #89b4fa;
    color: #1e1e2e;
}

/* 라벨 */
QLabel {
    color: #cdd6f4;
}

QLabel#title {
    font-size: 20px;
    font-weight: 800;
    color: #89b4fa;
    padding: 10px 0;
}

QLabel#subtitle {
    font-size: 14px;
    font-weight: 600;
    color: #a6adc8;
}

QLabel#status_connected {
    color: #a6e3a1; /* Green */
    font-weight: bold;
}
QLabel#status_disconnected {
    color: #f38ba8; /* Red */
    font-weight: bold;
}

QLabel#info_label {
    color: #9399b2;
    font-size: 12px;
}

/* 구분선 */
QFrame#separator {
    color: #45475a;
    background-color: #45475a;
    width: 2px;
}

/* 툴팁 */
QToolTip {
    border: 1px solid #89b4fa;
    background-color: #1e1e2e;
    color: #cdd6f4;
    padding: 8px;
    border-radius: 4px;
}
"""
