# -*- coding: utf-8 -*-
# pyright: reportAttributeAccessIssue=false, reportCallIssue=false, reportArgumentType=false
"""XPath Explorer mixin module (auto-split from legacy main file)."""


from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton

from xpath_explorer.core.constants import (
    BROWSER_CHECK_INTERVAL,
)


class ExplorerUIStatusPanelMixin:
    def _create_status_panel(self):
        """상태 패널"""
        self.status_layout = QHBoxLayout()
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.status_layout.addWidget(self.progress_bar, 1)
        
        # 구분선
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setObjectName("separator")
        self.status_layout.addWidget(sep)
        
        # 폰트 크기 조절
        btn_zoom_out = QPushButton("-")
        btn_zoom_out.setFixedSize(24, 24)
        btn_zoom_out.clicked.connect(self._decrease_font)
        
        btn_zoom_in = QPushButton("+")
        btn_zoom_in.setFixedSize(24, 24)
        btn_zoom_in.clicked.connect(self._increase_font)
        
        self.status_layout.addWidget(QLabel("글꼴:"))
        self.status_layout.addWidget(btn_zoom_out)
        self.status_layout.addWidget(btn_zoom_in)

    def _setup_timers(self):
        """주기적 작업 타이머"""
        self.check_timer = QTimer(self)
        self.check_timer.timeout.connect(self._check_browser)
        self.check_timer.start(BROWSER_CHECK_INTERVAL)
