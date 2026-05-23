# -*- coding: utf-8 -*-
# pyright: reportAttributeAccessIssue=false, reportCallIssue=false, reportArgumentType=false
"""XPath Explorer mixin module (auto-split from legacy main file)."""

import csv
import json
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from xpath_explorer.qt_compat import (
    QAction,
    QApplication,
    QAbstractItemView,
    QColor,
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
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    Qt,
    QTimer,
    QVBoxLayout,
    QWidget,
)

from xpath_explorer.core.constants import (
    WORKER_WAIT_TIMEOUT,
    category_to_label,
)
from xpath_explorer.core.config import XPathItem
from xpath_explorer.workers.background import (
    PickerWatcher,
    ValidateWorker,
    LivePreviewWorker,
    AIGenerateWorker,
    DiffAnalyzeWorker,
    BatchTestWorker,
    BatchScenarioWorker,
    InstallChromiumWorker,
)
from xpath_explorer.core.perf import perf_span, log_perf_summary
from xpath_explorer.tools.codegen import CodeTemplate, XPathTemplate
from xpath_explorer.browser.dom_export import (
    render_dom_report_htm,
    render_dom_diff_report_htm,
    diff_dom_snapshots,
)

from xpath_explorer.runtime import logger, error_telemetry


class ExplorerAIToolsMixin:
    def _show_ai_assistant(self):
        """AI XPath 추천 다이얼로그"""
        dialog = QDialog(self)
        dialog.setWindowTitle("🤖 AI XPath 추천")
        dialog.resize(600, 450)
        
        layout = QVBoxLayout(dialog)
        
        # API 상태
        if self.ai_assistant.is_available():
            provider = (self.ai_assistant._provider or "openai").capitalize()
            status_text = f"✅ {provider} API 연결됨"
            status_color = "#a6e3a1"
        else:
            status_text = "⚠️ API 키 미설정 (규칙 기반 모드)"
            status_color = "#fab387"
        
        lbl_status = QLabel(status_text)
        lbl_status.setStyleSheet(f"color: {status_color}; font-weight: bold;")
        layout.addWidget(lbl_status)
        
        # 입력
        layout.addWidget(QLabel("찾고자 하는 요소를 설명하세요:"))
        self._ai_input = QPlainTextEdit()
        self._ai_input.setMaximumHeight(80)
        self._ai_input.setPlaceholderText("예: 로그인 버튼, 이메일 입력창, 예매하기 링크...")
        layout.addWidget(self._ai_input)
        
        # 생성 버튼
        btn_generate = QPushButton("🔮 XPath 생성")
        btn_generate.setObjectName("primary")
        btn_generate.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(btn_generate)
        
        # 결과 영역
        layout.addWidget(QLabel("추천 결과:"))
        self._ai_result_text = QPlainTextEdit()
        self._ai_result_text.setReadOnly(True)
        self._ai_result_text.setStyleSheet("font-family: 'Consolas', monospace; background-color: #181825;")
        layout.addWidget(self._ai_result_text)
        
        # 신뢰도 라벨
        self._ai_confidence_label = QLabel("")
        layout.addWidget(self._ai_confidence_label)

        def _apply_ai_result(result):
            self._ai_last_xpath = result.xpath or ""
            output = f"추천 XPath:\n{result.xpath}\n\n"
            if result.alternative_xpaths:
                output += "대안:\n" + "\n".join(f"  - {x}" for x in result.alternative_xpaths) + "\n\n"
            output += f"설명:\n{result.explanation}"
            self._ai_result_text.setPlainText(output)
            
            conf = result.confidence * 100
            if conf >= 70:
                self._ai_confidence_label.setText(f"신뢰도: {conf:.0f}% (높음)")
                self._ai_confidence_label.setStyleSheet("color: #a6e3a1;")
            elif conf >= 40:
                self._ai_confidence_label.setText(f"신뢰도: {conf:.0f}% (보통)")
                self._ai_confidence_label.setStyleSheet("color: #fab387;")
            else:
                self._ai_confidence_label.setText(f"신뢰도: {conf:.0f}% (낮음)")
                self._ai_confidence_label.setStyleSheet("color: #f38ba8;")

        def _on_ai_generated(request_id: int, result):
            if request_id != self._ai_request_id:
                return
            _apply_ai_result(result)

        def _on_ai_failed(request_id: int, error: str):
            if request_id != self._ai_request_id:
                return
            self._ai_last_xpath = ""
            self._ai_result_text.setPlainText(f"생성 실패:\n{error}")
            self._ai_confidence_label.setText("")

        def _on_ai_worker_finished(worker):
            if self.ai_worker is worker:
                self.ai_worker = None
            btn_generate.setEnabled(True)
        
        def generate():
            with perf_span("ui.ai_generate_click"):
                desc = self._ai_input.toPlainText().strip()
                if not desc:
                    self._show_toast("설명을 입력하세요.", "warning")
                    return

                self._ai_request_id += 1
                request_id = self._ai_request_id

                if self.ai_worker and self.ai_worker.isRunning():
                    self.ai_worker.cancel()

                btn_generate.setEnabled(False)
                self._ai_last_xpath = ""
                self._ai_result_text.setPlainText("생성 중...")
                self._ai_confidence_label.setText("")

                worker = AIGenerateWorker(self.ai_assistant, desc, request_id)
                worker.generated.connect(_on_ai_generated)
                worker.failed.connect(_on_ai_failed)
                worker.finished.connect(lambda w=worker: _on_ai_worker_finished(w))
                self.ai_worker = worker
                worker.start()
        
        btn_generate.clicked.connect(generate)
        
        # 적용 버튼
        btn_layout = QHBoxLayout()
        
        btn_apply = QPushButton("📋 편집기에 적용")
        btn_apply.clicked.connect(lambda: (
            self.input_xpath.setPlainText(self._ai_last_xpath or ""),
            self._show_toast("XPath 적용됨", "success") if self._ai_last_xpath else self._show_toast("적용할 XPath가 없습니다.", "warning")
        ))
        btn_layout.addWidget(btn_apply)
        
        btn_settings = QPushButton("⚙️ API 설정")
        btn_settings.clicked.connect(lambda: self._configure_ai_api(dialog))
        btn_layout.addWidget(btn_settings)
        
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(dialog.reject)
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)
        dialog.finished.connect(
            lambda _=None: (
                self.ai_worker.cancel() if self.ai_worker and self.ai_worker.isRunning() else None
            )
        )
        dialog.exec()

    def _configure_ai_api(self, parent_dialog):
        """AI API 설정 (Provider 지원)"""
        dialog = QDialog(parent_dialog)
        dialog.setWindowTitle("⚙️ AI 설정")
        dialog.resize(400, 300)
        
        layout = QVBoxLayout(dialog)
        
        # Provider 선택
        layout.addWidget(QLabel("AI 제공자:"))
        combo_provider = QComboBox()
        combo_provider.addItems(["openai", "gemini"])
        combo_provider.setCurrentText(self.ai_assistant._provider)
        layout.addWidget(combo_provider)
        
        # API 키 입력
        layout.addWidget(QLabel("API 키:"))
        input_key = QLineEdit()
        input_key.setEchoMode(QLineEdit.EchoMode.Password)
        if self.ai_assistant._provider == "openai":
            input_key.setText(self.ai_assistant._config.get('openai_api_key', ''))
        else:
            input_key.setText(self.ai_assistant._config.get('gemini_api_key', ''))
        layout.addWidget(input_key)
        
        # Model 입력
        layout.addWidget(QLabel("모델:"))
        input_model = QLineEdit()
        input_model.setText(self.ai_assistant._model)
        layout.addWidget(input_model)
        
        # 힌트
        lbl_hint = QLabel(
            "앱 기본 OpenAI 모델: gpt-5.4\n"
            "예시 Gemini 모델: gemini-flash-latest, gemini-pro"
        )
        lbl_hint.setStyleSheet("color: #7f849c; font-size: 11px;")
        layout.addWidget(lbl_hint)
        
        # Provider 변경 시 처리
        def on_provider_change(text):
            input_key.clear()
            if text == "openai":
                input_key.setText(self.ai_assistant._config.get('openai_api_key', ''))
                input_model.setText("gpt-5.4")
            else:
                input_key.setText(self.ai_assistant._config.get('gemini_api_key', ''))
                input_model.setText("gemini-flash-latest")
                
        combo_provider.currentTextChanged.connect(on_provider_change)
        
        # 버튼 레이아웃
        btn_layout = QHBoxLayout()
        
        btn_save = QPushButton("저장")
        btn_save.setObjectName("success")
        def save():
            provider = combo_provider.currentText()
            key = input_key.text().strip()
            model = input_model.text().strip()
            
            if not key:
                self._show_toast("API 키를 입력하세요.", "warning")
                return

            result = self.ai_assistant.configure(key, model, provider)
            if not result.ok:
                self._show_toast(result.message, "error")
                return

            if result.config_saved:
                self._show_toast(
                    result.message or f"{provider} 설정이 저장되었습니다. ({result.storage_source})",
                    "success",
                )
            else:
                self._show_toast(result.message, "warning", 5000)
            dialog.accept()
            
        btn_save.clicked.connect(save)
        btn_layout.addWidget(btn_save)
        
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(dialog.reject)
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)
        
        dialog.exec()
