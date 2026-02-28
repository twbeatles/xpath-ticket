# -*- coding: utf-8 -*-
"""
XPath Explorer Stylesheet (Modern Dark Theme v3.6)
- Glassmorphism effects with enhanced depth
- Gradient buttons with animation
- Enhanced hover/focus states with smooth transitions
- Refined shadows and micro-interactions
- Improved accessibility contrast
"""

STYLE = """
/* ============================================
   Global Styles
   ============================================ */
* {
    font-family: 'Pretendard', 'Segoe UI', 'Malgun Gothic', sans-serif;
    font-size: 14px;
}

QMainWindow {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #1e1e2e, stop:1 #181825);
}

QWidget {
    background-color: transparent;
    color: #cdd6f4;
}

/* ============================================
   Tab Widget - Modern Pill Style
   ============================================ */
QTabWidget::pane {
    border: 1px solid rgba(69, 71, 90, 0.6);
    background: rgba(30, 30, 46, 0.9);
    border-radius: 12px;
    margin-top: -1px;
}

QTabBar {
    qproperty-drawBase: 0;
}

QTabBar::tab {
    background: rgba(24, 24, 37, 0.8);
    color: #a6adc8;
    padding: 10px 24px;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    margin-right: 4px;
    font-weight: 600;
    border: 1px solid transparent;
    border-bottom: none;
}

QTabBar::tab:selected {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #313244, stop:1 #252538);
    color: #ffffff;
    border: 1px solid #45475a;
    border-bottom: 3px solid #89b4fa;
}

QTabBar::tab:hover:!selected {
    background: rgba(49, 50, 68, 0.9);
    color: #cdd6f4;
}

/* ============================================
   Group Box - Glassmorphism Card Style
   ============================================ */
QGroupBox {
    border: 1px solid rgba(69, 71, 90, 0.5);
    border-radius: 12px;
    margin-top: 28px;
    padding: 20px 15px 15px 15px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 rgba(37, 37, 56, 0.95), stop:1 rgba(30, 30, 46, 0.9));
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top center;
    padding: 8px 20px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #89b4fa, stop:1 #cba6f7);
    border-radius: 16px;
    color: #1e1e2e;
    font-weight: bold;
    font-size: 13px;
}

/* ============================================
   Input Fields - Refined Focus States
   ============================================ */
QLineEdit, QPlainTextEdit, QTextEdit {
    background-color: rgba(49, 50, 68, 0.7);
    border: 1px solid #45475a;
    border-radius: 8px;
    padding: 10px 14px;
    color: #cdd6f4;
    selection-background-color: #89b4fa;
    selection-color: #1e1e2e;
}

QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {
    border: 2px solid #89b4fa;
    background-color: rgba(49, 50, 68, 0.9);
    padding: 9px 13px;
}

QLineEdit:hover, QPlainTextEdit:hover, QTextEdit:hover {
    border: 1px solid #585b70;
    background-color: rgba(49, 50, 68, 0.85);
}

QLineEdit::placeholder {
    color: #6c7086;
}

/* ============================================
   Buttons - Gradient & 3D Effect
   ============================================ */
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #45475a, stop:1 #313244);
    border: 1px solid #585b70;
    border-radius: 8px;
    padding: 10px 18px;
    color: #cdd6f4;
    font-weight: 600;
}

QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #585b70, stop:1 #45475a);
    border: 1px solid #6c7086;
}

QPushButton:pressed {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #313244, stop:1 #45475a);
    border: 1px solid #45475a;
}

QPushButton:disabled {
    background: rgba(24, 24, 37, 0.6);
    color: #585b70;
    border: 1px solid #313244;
}

/* Primary Button - Blue Gradient */
QPushButton#primary {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #89b4fa, stop:1 #74c7ec);
    color: #1e1e2e;
    border: none;
    font-weight: 700;
}
QPushButton#primary:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #b4befe, stop:1 #89b4fa);
}
QPushButton#primary:pressed {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #74c7ec, stop:1 #89dceb);
}

/* Success Button - Green Gradient */
QPushButton#success {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #a6e3a1, stop:1 #94e2d5);
    color: #1e1e2e;
    border: none;
    font-weight: 700;
}
QPushButton#success:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #b5f4a5, stop:1 #a6e3a1);
}

/* Danger Button - Red Gradient */
QPushButton#danger {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #f38ba8, stop:1 #eba0ac);
    color: #1e1e2e;
    border: none;
    font-weight: 700;
}
QPushButton#danger:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #f5a3b9, stop:1 #f38ba8);
}

/* Warning Button - Orange Gradient */
QPushButton#warning {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #fab387, stop:1 #f9e2af);
    color: #1e1e2e;
    border: none;
    font-weight: 700;
}
QPushButton#warning:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #fbc4a0, stop:1 #fab387);
}

/* Picker Button - Large Purple Gradient with Glow */
QPushButton#picker {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #cba6f7, stop:1 #f5c2e7);
    color: #1e1e2e;
    font-size: 16px;
    font-weight: 800;
    padding: 18px 36px;
    border-radius: 14px;
    border: none;
}
QPushButton#picker:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #dbb8ff, stop:1 #f5c2e7);
}
QPushButton#picker:pressed {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #b490e0, stop:1 #cba6f7);
}

/* Icon Button - Subtle */
QPushButton#icon_btn {
    background-color: transparent;
    border: none;
    padding: 8px;
    border-radius: 8px;
}
QPushButton#icon_btn:hover {
    background-color: rgba(137, 180, 250, 0.25);
    border: 1px solid rgba(137, 180, 250, 0.4);
}
QPushButton#icon_btn:pressed {
    background-color: rgba(137, 180, 250, 0.35);
}

/* ============================================
   ComboBox - Modern Dropdown
   ============================================ */
QComboBox {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 rgba(49, 50, 68, 0.9), stop:1 rgba(37, 37, 56, 0.9));
    border: 1px solid #45475a;
    border-radius: 8px;
    padding: 8px 14px;
    color: #cdd6f4;
    min-width: 100px;
}

QComboBox:hover {
    border: 1px solid #89b4fa;
    background: rgba(49, 50, 68, 0.95);
}

QComboBox:focus {
    border: 2px solid #89b4fa;
}

QComboBox::drop-down {
    border: none;
    width: 28px;
    background: transparent;
}

QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #a6adc8;
    margin-right: 10px;
}

QComboBox::down-arrow:hover {
    border-top: 6px solid #89b4fa;
}

QComboBox QAbstractItemView {
    background-color: #252538;
    border: 1px solid #45475a;
    border-radius: 8px;
    color: #cdd6f4;
    selection-background-color: #89b4fa;
    selection-color: #1e1e2e;
    padding: 5px;
    outline: none;
}

QComboBox QAbstractItemView::item {
    padding: 8px 12px;
    border-radius: 4px;
}

QComboBox QAbstractItemView::item:hover {
    background-color: rgba(137, 180, 250, 0.3);
}

/* ============================================
   Table Widget - Enhanced Rows
   ============================================ */
QTableWidget {
    background-color: rgba(30, 30, 46, 0.85);
    alternate-background-color: rgba(37, 37, 56, 0.65);
    gridline-color: rgba(49, 50, 68, 0.4);
    border: 1px solid rgba(69, 71, 90, 0.6);
    border-radius: 12px;
    selection-background-color: rgba(137, 180, 250, 0.35);
    outline: none;
}

QTableWidget::item {
    padding: 12px 10px;
    border-bottom: 1px solid rgba(49, 50, 68, 0.3);
    border-radius: 0;
}

QTableWidget::item:selected {
    background-color: rgba(137, 180, 250, 0.5);
    color: #ffffff;
    border-left: 4px solid #89b4fa;
}

QTableWidget::item:hover:!selected {
    background-color: rgba(69, 71, 90, 0.6);
}

QTableWidget::item:focus {
    outline: none;
    border: none;
}

QHeaderView::section {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 rgba(37, 37, 56, 0.95), stop:1 rgba(30, 30, 46, 0.95));
    padding: 14px 12px;
    border: none;
    border-bottom: 2px solid #89b4fa;
    color: #cdd6f4;
    font-weight: bold;
    font-size: 13px;
    letter-spacing: 0.5px;
}

QHeaderView::section:first {
    border-top-left-radius: 10px;
}

QHeaderView::section:last {
    border-top-right-radius: 10px;
}

QHeaderView::section:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #313244, stop:1 #252538);
}

/* ============================================
   Scrollbar - Minimal & Elegant
   ============================================ */
QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 10px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: rgba(69, 71, 90, 0.8);
    min-height: 40px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: rgba(88, 91, 112, 0.9);
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}

QScrollBar:horizontal {
    border: none;
    background: transparent;
    height: 10px;
    margin: 2px;
}
QScrollBar::handle:horizontal {
    background: rgba(69, 71, 90, 0.8);
    min-width: 40px;
    border-radius: 5px;
}
QScrollBar::handle:horizontal:hover {
    background: rgba(88, 91, 112, 0.9);
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
}

/* ============================================
   Menu Bar & Menus - Refined
   ============================================ */
QMenuBar {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #1e1e2e, stop:1 #181825);
    color: #cdd6f4;
    border-bottom: 1px solid #313244;
    padding: 2px 0;
}

QMenuBar::item {
    padding: 8px 14px;
    background: transparent;
    border-radius: 6px;
    margin: 2px 4px;
}

QMenuBar::item:selected {
    background: rgba(137, 180, 250, 0.3);
    color: #ffffff;
}

QMenu {
    background-color: rgba(37, 37, 56, 0.98);
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 10px;
    padding: 8px 5px;
}

QMenu::item {
    padding: 10px 30px 10px 20px;
    border-radius: 6px;
    margin: 2px 5px;
}

QMenu::item:selected {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #89b4fa, stop:1 #b4befe);
    color: #1e1e2e;
}

QMenu::separator {
    height: 1px;
    background: #45475a;
    margin: 8px 15px;
}

QMenu::icon {
    padding-left: 10px;
}

/* ============================================
   Labels - Various Styles
   ============================================ */
QLabel {
    color: #cdd6f4;
    background: transparent;
}

QLabel#title {
    font-size: 22px;
    font-weight: 800;
    color: #89b4fa;
    padding: 12px 0;
}

/* ============================================
   Search Input - Premium Style
   ============================================ */
QLineEdit#search_input {
    background-color: rgba(37, 37, 56, 0.95);
    border: 2px solid rgba(69, 71, 90, 0.7);
    border-radius: 12px;
    padding: 12px 18px 12px 40px;
    color: #cdd6f4;
    font-size: 14px;
}

QLineEdit#search_input:focus {
    border: 2px solid #89b4fa;
    background-color: rgba(49, 50, 68, 1);
}

QLineEdit#search_input:hover:!focus {
    border: 2px solid rgba(137, 180, 250, 0.5);
    background-color: rgba(37, 37, 56, 1);
}

/* ============================================
   Large URL Input - High Visibility
   ============================================ */
QLineEdit#url_input_large {
    background-color: rgba(30, 30, 46, 0.95);
    border: 2px solid #585b70;
    border-radius: 8px;
    padding: 10px 16px;
    color: #cdd6f4;
    font-size: 16px;
    font-weight: 500;
}

QLineEdit#url_input_large:focus {
    border: 2px solid #89b4fa;
    background-color: rgba(49, 50, 68, 1);
}

QLineEdit#url_input_large:hover:!focus {
    border: 2px solid #7f849c;
}


QLabel#subtitle {
    font-size: 14px;
    font-weight: 600;
    color: #a6adc8;
}

QLabel#status_connected {
    color: #a6e3a1;
    font-weight: bold;
    font-size: 13px;
    text-shadow: 0 0 8px rgba(166, 227, 161, 0.6);
}

QLabel#status_disconnected {
    color: #f38ba8;
    font-weight: bold;
    font-size: 13px;
}

QLabel#info_label {
    color: #9399b2;
    font-size: 12px;
}

/* ============================================
   Separator - Refined
   ============================================ */
QFrame#separator {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 transparent, stop:0.5 #45475a, stop:1 transparent);
    border: none;
    max-width: 1px;
    min-width: 1px;
    margin: 5px 8px;
}

/* ============================================
   Checkbox - Custom Style
   ============================================ */
QCheckBox {
    spacing: 8px;
    color: #cdd6f4;
}

QCheckBox::indicator {
    width: 20px;
    height: 20px;
    border-radius: 5px;
    border: 2px solid #45475a;
    background: rgba(49, 50, 68, 0.6);
}

QCheckBox::indicator:hover {
    border: 2px solid #89b4fa;
    background: rgba(137, 180, 250, 0.2);
}

QCheckBox::indicator:checked {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #89b4fa, stop:1 #cba6f7);
    border: 2px solid #89b4fa;
}

QCheckBox::indicator:checked:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #b4befe, stop:1 #dbb8ff);
}

/* ============================================
   Progress Bar - Gradient Fill
   ============================================ */
QProgressBar {
    border: none;
    border-radius: 6px;
    background: rgba(24, 24, 37, 0.8);
    height: 12px;
    text-align: center;
    color: #cdd6f4;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #89b4fa, stop:0.5 #cba6f7, stop:1 #f5c2e7);
    border-radius: 6px;
}

/* ============================================
   Tooltip - Modern Floating
   ============================================ */
QToolTip {
    border: 1px solid #89b4fa;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #252538, stop:1 #1e1e2e);
    color: #cdd6f4;
    padding: 10px 14px;
    border-radius: 8px;
    font-size: 13px;
}

/* ============================================
   Splitter Handle
   ============================================ */
QSplitter::handle {
    background: rgba(69, 71, 90, 0.4);
    width: 3px;
    border-radius: 1px;
}

QSplitter::handle:hover {
    background: #89b4fa;
}

/* ============================================
   Dialog Buttons
   ============================================ */
QDialogButtonBox {
    button-layout: 3;
}

QDialogButtonBox QPushButton {
    min-width: 90px;
    min-height: 32px;
}

/* ============================================
   List Widget
   ============================================ */
QListWidget {
    background: rgba(30, 30, 46, 0.8);
    border: 1px solid #45475a;
    border-radius: 8px;
    outline: none;
}

QListWidget::item {
    padding: 10px 14px;
    border-radius: 6px;
    margin: 2px 4px;
}

QListWidget::item:selected {
    background: rgba(137, 180, 250, 0.4);
    color: #ffffff;
}

QListWidget::item:hover {
    background: rgba(69, 71, 90, 0.5);
}

/* ============================================
   Spin Box
   ============================================ */
QSpinBox {
    background: rgba(49, 50, 68, 0.7);
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px 10px;
    color: #cdd6f4;
}

QSpinBox:focus {
    border: 2px solid #89b4fa;
}

QSpinBox::up-button, QSpinBox::down-button {
    background: transparent;
    border: none;
    width: 20px;
}

/* ============================================
   Status Indicator - Animated Pulse
   ============================================ */
QLabel#status_connected {
    color: #a6e3a1;
    font-weight: bold;
    font-size: 13px;
    padding: 4px 12px;
    background: rgba(166, 227, 161, 0.15);
    border-radius: 16px;
    border: 1px solid rgba(166, 227, 161, 0.3);
}

QLabel#status_disconnected {
    color: #f38ba8;
    font-weight: bold;
    font-size: 13px;
    padding: 4px 12px;
    background: rgba(243, 139, 168, 0.15);
    border-radius: 16px;
    border: 1px solid rgba(243, 139, 168, 0.3);
}

/* ============================================
   Modern Card - Glassmorphism
   ============================================ */
QFrame#card {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 rgba(49, 50, 68, 0.9), stop:1 rgba(37, 37, 56, 0.85));
    border: 1px solid rgba(69, 71, 90, 0.6);
    border-radius: 14px;
    padding: 16px;
}

QFrame#card:hover {
    border: 1px solid rgba(137, 180, 250, 0.5);
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 rgba(49, 50, 68, 0.95), stop:1 rgba(37, 37, 56, 0.9));
}

/* ============================================
   Empty State - Centered Message
   ============================================ */
QLabel#empty_state {
    color: #7f849c;
    font-size: 15px;
    font-weight: 600;
    padding: 40px;
    qproperty-alignment: 'AlignCenter';
}

QLabel#empty_state_icon {
    font-size: 48px;
    color: #585b70;
    qproperty-alignment: 'AlignCenter';
}

/* ============================================
   Action Button Group
   ============================================ */
QPushButton#action_btn {
    background: transparent;
    border: 1px solid rgba(69, 71, 90, 0.6);
    border-radius: 8px;
    padding: 8px 14px;
    color: #a6adc8;
    font-weight: 600;
}

QPushButton#action_btn:hover {
    background: rgba(137, 180, 250, 0.15);
    border: 1px solid rgba(137, 180, 250, 0.5);
    color: #89b4fa;
}

QPushButton#action_btn:pressed {
    background: rgba(137, 180, 250, 0.25);
}

/* ============================================
   Badge Styles
   ============================================ */
QLabel#badge_success {
    background: rgba(166, 227, 161, 0.2);
    color: #a6e3a1;
    border-radius: 10px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: bold;
}

QLabel#badge_warning {
    background: rgba(250, 179, 135, 0.2);
    color: #fab387;
    border-radius: 10px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: bold;
}

QLabel#badge_error {
    background: rgba(243, 139, 168, 0.2);
    color: #f38ba8;
    border-radius: 10px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: bold;
}

QLabel#badge_info {
    background: rgba(137, 180, 250, 0.2);
    color: #89b4fa;
    border-radius: 10px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: bold;
}

/* ============================================
   Toolbar - Modern Style
   ============================================ */
QToolBar {
    background: transparent;
    border: none;
    spacing: 8px;
    padding: 4px;
}

QToolButton {
    background: rgba(49, 50, 68, 0.7);
    border: 1px solid rgba(69, 71, 90, 0.5);
    border-radius: 8px;
    padding: 8px;
    color: #cdd6f4;
}

QToolButton:hover {
    background: rgba(137, 180, 250, 0.2);
    border: 1px solid #89b4fa;
}

QToolButton:pressed {
    background: rgba(137, 180, 250, 0.35);
}

/* ============================================
   Enhanced Dialogs
   ============================================ */
QDialog {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #1e1e2e, stop:1 #181825);
}

QDialog QLabel {
    color: #cdd6f4;
}

QDialog QGroupBox {
    border: 1px solid rgba(69, 71, 90, 0.5);
    border-radius: 10px;
    margin-top: 24px;
    padding: 16px 12px 12px 12px;
    background: rgba(37, 37, 56, 0.6);
}

QDialog QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 6px 14px;
    background: rgba(137, 180, 250, 0.2);
    border-radius: 8px;
    color: #89b4fa;
    font-weight: bold;
    font-size: 12px;
    left: 12px;
}
"""

