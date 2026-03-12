"""Minimal PyQt6 compatibility layer for headless test environments."""
# pyright: reportAssignmentType=false

from __future__ import annotations

from typing import TYPE_CHECKING

QT_AVAILABLE = True
QT_IMPORT_ERROR: ImportError | None = None

if TYPE_CHECKING:
    from PyQt6.QtCore import (
        QEasingCurve,
        QMimeData,
        QPropertyAnimation,
        QSettings,
        QSize,
        Qt,
        QThread,
        QTimer,
        pyqtSignal,
    )
    from PyQt6.QtGui import QAction, QColor, QDrag, QFont, QIcon, QKeySequence, QPalette, QPixmap
    from PyQt6.QtWidgets import (
        QApplication,
        QAbstractItemView,
        QCheckBox,
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QFileDialog,
        QFormLayout,
        QFrame,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QHeaderView,
        QInputDialog,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMenu,
        QMenuBar,
        QMessageBox,
        QPlainTextEdit,
        QProgressBar,
        QPushButton,
        QScrollArea,
        QSizePolicy,
        QSpinBox,
        QSplitter,
        QStackedWidget,
        QTableView,
        QTableWidget,
        QTableWidgetItem,
        QTabWidget,
        QTextEdit,
        QToolBar,
        QToolButton,
        QTreeWidget,
        QTreeWidgetItem,
        QVBoxLayout,
        QWidget,
    )
else:
    try:
        from PyQt6.QtCore import (
            QEasingCurve,
            QMimeData,
            QPropertyAnimation,
            QSettings,
            QSize,
            Qt,
            QThread,
            QTimer,
            pyqtSignal,
        )
        from PyQt6.QtGui import QAction, QColor, QDrag, QFont, QIcon, QKeySequence, QPalette, QPixmap
        from PyQt6.QtWidgets import (
            QApplication,
            QAbstractItemView,
            QCheckBox,
            QComboBox,
            QDialog,
            QDialogButtonBox,
            QFileDialog,
            QFormLayout,
            QFrame,
            QGridLayout,
            QGroupBox,
            QHBoxLayout,
            QHeaderView,
            QInputDialog,
            QLabel,
            QLineEdit,
            QListWidget,
            QListWidgetItem,
            QMainWindow,
            QMenu,
            QMenuBar,
            QMessageBox,
            QPlainTextEdit,
            QProgressBar,
            QPushButton,
            QScrollArea,
            QSizePolicy,
            QSpinBox,
            QSplitter,
            QStackedWidget,
            QTableView,
            QTableWidget,
            QTableWidgetItem,
            QTabWidget,
            QTextEdit,
            QToolBar,
            QToolButton,
            QTreeWidget,
            QTreeWidgetItem,
            QVBoxLayout,
            QWidget,
        )
    except ImportError as exc:
        QT_AVAILABLE = False
        QT_IMPORT_ERROR = exc

if not QT_AVAILABLE:
    class _Signal:
        def connect(self, *_args, **_kwargs):
            return None

        def emit(self, *_args, **_kwargs):
            return None

    def pyqtSignal(*_args, **_kwargs):
        return _Signal()

    class _QtStub:
        def __init__(self, *_args, **_kwargs):
            pass

        def __getattr__(self, _name):
            return _Signal()

        def __call__(self, *_args, **_kwargs):
            return None

    class _Clipboard:
        def setText(self, _text):
            return None

    class QApplication(_QtStub):
        @staticmethod
        def clipboard():
            return _Clipboard()

        @staticmethod
        def instance():
            return None

        def exec(self):
            return 0

        def setStyle(self, *_args, **_kwargs):
            return None

        def setFont(self, *_args, **_kwargs):
            return None

    class QFileDialog:
        @staticmethod
        def getOpenFileName(*_args, **_kwargs):
            return ("", "")

        @staticmethod
        def getSaveFileName(*_args, **_kwargs):
            return ("", "")

    class QMessageBox:
        class StandardButton:
            Yes = 1
            No = 2
            Close = 3

        @staticmethod
        def question(*_args, **_kwargs):
            return QMessageBox.StandardButton.No

        @staticmethod
        def warning(*_args, **_kwargs):
            return None

        @staticmethod
        def information(*_args, **_kwargs):
            return None

        @staticmethod
        def about(*_args, **_kwargs):
            return None

    class QDialogButtonBox(_QtStub):
        class StandardButton:
            Close = 0

        class ButtonRole:
            AcceptRole = 0
            ResetRole = 1

        def addButton(self, *_args, **_kwargs):
            return _QtStub()

    class QHeaderView(_QtStub):
        class ResizeMode:
            Interactive = 0
            Stretch = 1
            ResizeToContents = 2

    class Qt:
        class AlignmentFlag:
            AlignCenter = 0
            AlignRight = 0

        class CheckState:
            class Checked:
                value = 2

        class ContextMenuPolicy:
            CustomContextMenu = 0

        class CursorShape:
            PointingHandCursor = 0

        class ItemDataRole:
            UserRole = 1000
            DisplayRole = 0
            TextAlignmentRole = 1
            ForegroundRole = 2
            BackgroundRole = 3
            ToolTipRole = 4

        class Key:
            Key_Escape = 0

        class Orientation:
            Horizontal = 0

        class ScrollBarPolicy:
            ScrollBarAlwaysOff = 0

    QEasingCurve = QMimeData = QPropertyAnimation = QSettings = QSize = QThread = QTimer = _QtStub
    QAction = QColor = QDrag = QFont = QIcon = QKeySequence = QPalette = QPixmap = _QtStub
    QAbstractItemView = QCheckBox = QComboBox = QDialog = QFormLayout = QFrame = _QtStub
    QGridLayout = QGroupBox = QHBoxLayout = QLabel = QLineEdit = QListWidget = _QtStub
    QListWidgetItem = QInputDialog = QMainWindow = QMenu = QMenuBar = QPlainTextEdit = _QtStub
    QProgressBar = QPushButton = QScrollArea = QSizePolicy = QSpinBox = _QtStub
    QSplitter = QStackedWidget = QTableView = QTableWidget = QTableWidgetItem = _QtStub
    QTabWidget = QTextEdit = QToolBar = QToolButton = QTreeWidget = QTreeWidgetItem = _QtStub
    QVBoxLayout = QWidget = _QtStub


def require_qt() -> None:
    """Raise a clear error when GUI code is used without a working Qt runtime."""
    if QT_IMPORT_ERROR is not None:
        raise RuntimeError(
            "PyQt6 GUI components are unavailable in this environment."
        ) from QT_IMPORT_ERROR
