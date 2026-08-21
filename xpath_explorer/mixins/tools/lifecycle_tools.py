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
from xpath_explorer.workers.driver_guard import exclusive_driver_worker_running


class ExplorerLifecycleToolsMixin:
    def _stop_live_preview_sync(self):
        worker = getattr(self, "live_preview_worker", None)
        if worker is None:
            return
        try:
            if worker.isRunning():
                cancel_fn = getattr(worker, "cancel", None)
                if callable(cancel_fn):
                    cancel_fn()
                worker.wait(WORKER_WAIT_TIMEOUT)
        except Exception:
            pass

    def _abort_if_driver_busy(self, action_label: str) -> bool:
        busy, name = exclusive_driver_worker_running(self)
        if not busy:
            return False
        self._show_toast(f"{action_label}을(를) 진행할 수 없습니다. 다른 브라우저 작업이 실행 중입니다 ({name}).", "warning")
        return True

    def keyPressEvent(self, a0):
        """키보드 이벤트 처리 - ESC로 배치 테스트 취소"""
        if a0.key() == Qt.Key.Key_Escape:
            if self.batch_worker and self.batch_worker.isRunning():
                self.batch_worker.cancel()
        super().keyPressEvent(a0)

    def _stop_worker_thread(self, worker: Any, worker_name: str, timeout: int = WORKER_WAIT_TIMEOUT):
        if worker is None:
            return
        try:
            if not worker.isRunning():
                return
        except Exception:
            return

        try:
            cancel_fn = getattr(worker, "cancel", None)
            stop_fn = getattr(worker, "stop", None)
            if callable(cancel_fn):
                cancel_fn()
            elif callable(stop_fn):
                stop_fn()

            wait_fn = getattr(worker, "wait", None)
            if callable(wait_fn):
                waited = wait_fn(timeout)
                if waited is False:
                    logger.warning(f"{worker_name} 종료 대기 타임아웃")
                    disconnect_fn = getattr(worker, "disconnect", None)
                    if callable(disconnect_fn):
                        try:
                            disconnect_fn()
                        except Exception:
                            pass
        except Exception as e:
            logger.warning(f"{worker_name} 종료 중 예외: {e}")

    def closeEvent(self, a0):
        """종료 처리"""
        logger.info("앱 종료 시작...")

        try:
            confirm = getattr(self, "_confirm_discard_unsaved", None)
            if callable(confirm) and not confirm("종료"):
                a0.ignore()
                return

            check_timer = getattr(self, "check_timer", None)
            if check_timer is not None:
                check_timer.stop()

            if hasattr(self, "settings") and self.settings is not None:
                self.settings.setValue("geometry", self.saveGeometry())
            self._save_settings()

            self._stop_worker_thread(getattr(self, "picker_watcher", None), "PickerWatcher")
            self._stop_worker_thread(getattr(self, "validate_worker", None), "ValidateWorker")
            self._stop_worker_thread(getattr(self, "live_preview_worker", None), "LivePreviewWorker")
            self._stop_worker_thread(getattr(self, "ai_worker", None), "AIWorker")
            self._stop_worker_thread(getattr(self, "diff_worker", None), "DiffWorker")
            self._stop_worker_thread(getattr(self, "batch_worker", None), "BatchWorker")
            self._stop_worker_thread(getattr(self, "scenario_worker", None), "BatchScenarioWorker")
            self._stop_worker_thread(
                getattr(self, "playwright_install_worker", None),
                "InstallChromiumWorker",
            )
            self.picker_watcher = None
            self.validate_worker = None
            self.live_preview_worker = None
            self.ai_worker = None
            self.diff_worker = None
            self.batch_worker = None
            self.scenario_worker = None
            self.playwright_install_worker = None

            pw_manager = getattr(self, "pw_manager", None)
            if pw_manager is not None:
                try:
                    pw_manager.close()
                except Exception as e:
                    logger.warning(f"Playwright 종료 실패(무시): {e}")

            stats_manager = getattr(self, "stats_manager", None)
            if stats_manager is not None:
                try:
                    stats_manager.shutdown(timeout=5.0)
                except Exception:
                    try:
                        stats_manager.save()
                    except Exception:
                        pass

            try:
                log_perf_summary()
            except Exception:
                pass

            browser = getattr(self, "browser", None)
            if browser is not None:
                try:
                    browser.close()
                except Exception as e:
                    logger.warning(f"브라우저 종료 실패(무시): {e}")
        finally:
            logger.info("앱 종료 완료")
            a0.accept()
