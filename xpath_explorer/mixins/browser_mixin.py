# -*- coding: utf-8 -*-
"""XPath Explorer mixin module (auto-split from legacy main file)."""

import csv
import json
import os
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING, Tuple, cast

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit, QComboBox, QCheckBox,
    QTableWidget, QTableWidgetItem, QTabWidget, QSplitter, QGroupBox,
    QProgressBar, QMenu, QToolBar, QDialog, QDialogButtonBox,
    QListWidget, QListWidgetItem, QMessageBox, QFileDialog, QHeaderView,
    QAbstractItemView, QSpinBox, QFormLayout, QScrollArea, QFrame, QTableView,
    QTreeWidget, QTreeWidgetItem, QPlainTextEdit, QStackedWidget, QMenuBar,
    QToolButton, QGridLayout, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize, QSettings, QPropertyAnimation, QEasingCurve, QMimeData
from PyQt6.QtGui import QFont, QColor, QAction, QPalette, QIcon, QPixmap, QKeySequence, QDrag

from xpath_explorer.core.constants import (
    APP_TITLE, APP_VERSION, SITE_PRESETS,
    BROWSER_CHECK_INTERVAL, SEARCH_DEBOUNCE_MS,
    LIVE_PREVIEW_DEBOUNCE_MS, WORKER_WAIT_TIMEOUT,
)
from xpath_explorer.ui.styles import STYLE
from xpath_explorer.core.config import XPathItem, SiteConfig
from xpath_explorer.ui.widgets import ToastWidget, NoWheelComboBox, AnimatedStatusIndicator, IconButton, CollapsibleBox
from xpath_explorer.browser.browser import BrowserManager
from xpath_explorer.workers.background import (
    PickerWatcher, ValidateWorker, LivePreviewWorker,
    AIGenerateWorker, DiffAnalyzeWorker, BatchTestWorker,
)
from xpath_explorer.core.perf import perf_span, log_perf_summary
from xpath_explorer.tools.codegen import CodeGenerator, CodeTemplate
from xpath_explorer.analysis.statistics import StatisticsManager
from xpath_explorer.tools.optimizer import XPathOptimizer, XPathAlternative
from xpath_explorer.state.history import HistoryManager
from xpath_explorer.tools.ai import XPathAIAssistant
from xpath_explorer.analysis.diff import XPathDiffAnalyzer
from xpath_explorer.ui.table_model import XPathItemTableModel
from xpath_explorer.ui.filter_proxy import XPathFilterProxyModel
from xpath_explorer.browser.dom_export import render_dom_report_htm

from xpath_explorer.runtime import logger


class ExplorerBrowserMixin:
    # NOTE:
    # This mixin is composed into XPathExplorer (QMainWindow). These declarations
    # are type-checking only so Pylance can resolve cross-mixin attributes/methods.
    if TYPE_CHECKING:
        browser: BrowserManager
        status_indicator: AnimatedStatusIndicator
        lbl_status: QLabel
        btn_open: QPushButton
        combo_windows: QComboBox
        combo_frames: QComboBox
        config: SiteConfig
        input_url: QLineEdit
        input_xpath: QPlainTextEdit
        input_css: QLineEdit
        input_desc: QLineEdit
        input_name: QLineEdit
        txt_result: QTextEdit
        chk_overlay: QCheckBox
        btn_picker_lock: QPushButton
        btn_picker_unlock: QPushButton
        progress_bar: QProgressBar
        lbl_live_preview: QLabel

        stats_manager: StatisticsManager
        table_model: XPathItemTableModel
        diff_analyzer: XPathDiffAnalyzer

        picker_watcher: Optional[PickerWatcher]
        validate_worker: Optional[ValidateWorker]
        live_preview_worker: Optional[LivePreviewWorker]
        _live_preview_timer: QTimer
        _live_preview_request_id: int
        _frame_selection_explicit: bool
        _last_browser_state: Optional[bool]
        _last_window_count: int

        def _show_toast(self, message: str, toast_type: str = "info", duration: int = 3000) -> None: ...
        def _refresh_table(self, filter_cat: Optional[str] = None, refresh_filters: bool = False) -> None: ...
        def _add_to_history(self, xpath: str, css: str, tag: str, frame: str) -> None: ...
        def show(self) -> None: ...
        def hide(self) -> None: ...

    def _set_picker_action_enabled(self, enabled: bool):
        """요소 선택기 고정/해제 버튼 활성 상태 동기화."""
        btn_lock = getattr(self, "btn_picker_lock", None)
        if btn_lock is not None:
            btn_lock.setEnabled(enabled)
        btn_unlock = getattr(self, "btn_picker_unlock", None)
        if btn_unlock is not None:
            btn_unlock.setEnabled(enabled)

    def _get_frame_combo_path(self) -> str:
        combo = self.__dict__.get("combo_frames")
        if combo is None:
            return "main"
        index = combo.currentIndex()
        if index < 0:
            return "main"
        data = combo.itemData(index)
        if isinstance(data, str) and data:
            return data
        return "main"

    def _set_frame_combo_path(self, frame_path: Optional[str], explicit: Optional[bool] = None):
        combo = self.__dict__.get("combo_frames")
        if combo is None:
            if explicit is not None:
                self._frame_selection_explicit = explicit
            return

        target = frame_path or "main"
        index = combo.findData(target)
        if index < 0:
            target = "main"
            index = combo.findData(target)
        if index < 0 and combo.count() > 0:
            index = 0

        combo.blockSignals(True)
        try:
            if index >= 0:
                combo.setCurrentIndex(index)
        finally:
            combo.blockSignals(False)

        if explicit is not None:
            self._frame_selection_explicit = explicit

    def _get_current_item(self) -> Optional[XPathItem]:
        name_widget = self.__dict__.get("input_name")
        if name_widget is None or not hasattr(name_widget, "text"):
            return None
        name = str(name_widget.text() or "").strip()
        if not name:
            return None
        return self.config.get_item(name)

    def _resolve_active_frame_path(self) -> Optional[str]:
        combo_frame = self._get_frame_combo_path()
        if getattr(self, "_frame_selection_explicit", False):
            return combo_frame or "main"

        item = self._get_current_item()
        if item is not None and item.found_frame:
            return item.found_frame

        if combo_frame and combo_frame != "main":
            return combo_frame
        return None

    def _validate_xpath_for_ui(self, xpath: str, frame_path: Optional[str]) -> Dict[str, Any]:
        if frame_path is None:
            return cast(Dict[str, Any], self.browser.validate_xpath(xpath))

        try:
            try:
                info = self.browser.get_element_info(xpath, frame_path=frame_path, include_attributes=False)
            except TypeError:
                info = self.browser.get_element_info(xpath, frame_path=frame_path)
        except Exception as e:
            return {"found": False, "msg": str(e), "frame_path": frame_path}

        if not info or not info.get("found"):
            return {
                "found": False,
                "msg": str((info or {}).get("msg") or getattr(self.browser, "last_error", "") or "요소를 찾을 수 없습니다."),
                "frame_path": str((info or {}).get("frame_path", frame_path) or frame_path or ""),
            }

        return {
            "found": True,
            "count": int(info.get("count", 1) or 1),
            "tag": info.get("tag", ""),
            "text": info.get("text", ""),
            "frame_path": str(info.get("frame_path", frame_path) or frame_path or "main"),
            "msg": "",
        }

    def _set_live_preview_error(self, message: str):
        detail = (message or "").strip()
        if detail and len(detail) > 28:
            display = detail[:25] + "..."
        else:
            display = detail or "오류"
        self.lbl_live_preview.setText(f"⚠️ {display}")
        self.lbl_live_preview.setToolTip(detail)
        self.lbl_live_preview.setStyleSheet("color: #f38ba8; font-size: 11px;")

    def _check_browser(self):
        """브라우저 연결 상태 주기적 확인 (popup/window 변화 포함)."""
        is_alive = self.browser.is_alive()
        current_state = getattr(self, '_last_browser_state', None)

        window_count = 0
        if is_alive and self.browser.driver is not None:
            try:
                window_count = len(self.browser.driver.window_handles)
            except Exception:
                window_count = 0

        # 상태는 같아도 popup/window 수 변화가 있으면 목록을 갱신한다.
        if current_state == is_alive:
            last_window_count = getattr(self, "_last_window_count", 0)
            if is_alive and window_count != last_window_count:
                self._last_window_count = window_count
                popup_opened = window_count > last_window_count
                self._refresh_windows(prefer_popup=popup_opened)
                if popup_opened and window_count > 1:
                    self._show_toast("새 팝업 창을 감지했습니다.", "info", 1800)
            return

        self._last_browser_state = is_alive
        self._last_window_count = window_count

        # AnimatedStatusIndicator 업데이트
        self.status_indicator.set_connected(is_alive)

        if is_alive:
            self.lbl_status.setText(f"{self.config.name}")
            self.lbl_status.setObjectName("status_connected")
            self.btn_open.setText("🔴 브라우저 닫기")
            self.btn_open.setObjectName("danger")
            self._refresh_windows(prefer_popup=True)
        else:
            self.lbl_status.setText("연결 안됨")
            self.lbl_status.setObjectName("status_disconnected")
            self.btn_open.setText("🌐 브라우저 열기")
            self.btn_open.setObjectName("primary")
            self.combo_windows.clear()
            self.combo_frames.clear()
            self._frame_selection_explicit = False
            self._last_window_count = 0
            self._set_picker_action_enabled(False)

        # 스타일 리로드 (색상 변경 적용)
        status_style = self.lbl_status.style()
        if status_style is not None:
            status_style.unpolish(self.lbl_status)
            status_style.polish(self.lbl_status)
        button_style = self.btn_open.style()
        if button_style is not None:
            button_style.unpolish(self.btn_open)
            button_style.polish(self.btn_open)

    def _toggle_browser(self):
        """브라우저 열기/닫기"""
        if self.browser.is_alive():
            if self.picker_watcher:
                self.picker_watcher.stop()
                self.picker_watcher.wait(WORKER_WAIT_TIMEOUT)
                self.picker_watcher = None
            self.browser.close()
            self._set_picker_action_enabled(False)
            self._show_toast("브라우저가 종료되었습니다.", "info")
        else:
            # 설정의 URL 사용
            start_url = self.config.login_url or self.config.url
            if not start_url:
                start_url = "about:blank"
                
            self._show_toast("브라우저를 시작합니다...", "info", 5000)
            
            if self.browser.create_driver():
                self.browser.navigate(start_url)
                self.input_url.setText(start_url)
                self._refresh_windows()
                self._show_toast("브라우저가 실행되었습니다.", "success")
            else:
                last_error = getattr(self.browser, "last_error", "")
                self._show_toast(last_error or "브라우저 실행 실패. 드라이버를 확인하세요.", "error")

    def _navigate(self):
        """URL 이동"""
        url = self.input_url.text().strip()
        if not url: return
        
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            self.input_url.setText(url)  # 정규화된 URL로 입력창 업데이트
            
        if self.browser.is_alive():
            self.browser.navigate(url)
            self._show_toast(f"이동 중: {url}", "info")
        else:
            self._show_toast("브라우저가 실행되지 않았습니다.", "warning")

    def _browser_back(self):
        if not self.browser.is_alive():
            return
        driver = self.browser.driver
        if driver is not None:
            driver.back()

    def _browser_forward(self):
        if not self.browser.is_alive():
            return
        driver = self.browser.driver
        if driver is not None:
            driver.forward()

    def _browser_refresh(self):
        if not self.browser.is_alive():
            return
        driver = self.browser.driver
        if driver is not None:
            driver.refresh()

    def _refresh_windows(self, prefer_popup: bool = False):
        """윈도우 목록 갱신 (팝업 우선 정렬 + 선택 유지)."""
        selected_handle = None
        current_index = self.combo_windows.currentIndex()
        if current_index >= 0:
            selected_handle = self.combo_windows.itemData(current_index)

        self.combo_windows.blockSignals(True)
        self.combo_windows.clear()

        windows = self.browser.get_windows()
        handles: List[str] = []
        popup_handle = None
        current_handle = None

        for i, win in enumerate(windows):
            title = win['title'] if win['title'] else f"창 {i+1}"
            if len(title) > 30:
                title = title[:27] + "..."

            is_popup = bool(win.get("is_popup"))
            label_prefix = "[팝업] " if is_popup else ""
            self.combo_windows.addItem(f"{label_prefix}{title}", win['handle'])
            handles.append(win['handle'])

            if is_popup and popup_handle is None:
                popup_handle = win['handle']
            if win.get('current'):
                current_handle = win['handle']

        target_handle = None
        if selected_handle in handles:
            target_handle = selected_handle
        elif prefer_popup and popup_handle:
            target_handle = popup_handle
        elif current_handle in handles:
            target_handle = current_handle
        elif popup_handle:
            target_handle = popup_handle
        elif handles:
            target_handle = handles[0]

        if target_handle in handles:
            target_idx = handles.index(target_handle)
            self.combo_windows.setCurrentIndex(target_idx)

        self.combo_windows.blockSignals(False)

        if target_handle:
            try:
                driver = self.browser.driver
                current_driver_handle = driver.current_window_handle if driver is not None else None
            except Exception:
                current_driver_handle = None

            if target_handle != current_driver_handle:
                self.browser.switch_window(target_handle)

        self._scan_frames()

    def _on_window_changed(self, index):
        """윈도우 전환"""
        if index < 0: return
        
        handle = self.combo_windows.itemData(index)
        if self.browser.switch_window(handle):
            self._scan_frames()
            self._show_toast("윈도우가 전환되었습니다.", "success")
        else:
            self._show_toast("윈도우 전환 실패", "error")
            self._refresh_windows()

    def _on_frame_changed(self, index):
        """프레임 전환"""
        if index < 0:
            self._frame_selection_explicit = False
            return

        target_frame = self._get_frame_combo_path()
        self._frame_selection_explicit = True

        if not self.browser.is_alive():
            return

        if self.browser.switch_to_frame_by_path(target_frame):
            self._show_toast("프레임이 전환되었습니다.", "success")
        else:
            last_error = getattr(self.browser, "last_error", "")
            self._show_toast(last_error or "프레임 전환 실패", "error")

    def _scan_frames(self):
        """iframe 목록 스캔"""
        with perf_span("ui.scan_frames"):
            manual_target = self._get_frame_combo_path() if getattr(self, "_frame_selection_explicit", False) else None
            self.combo_frames.blockSignals(True)
            try:
                self.combo_frames.clear()
                self.combo_frames.addItem("메인 문서", "main")
                
                if not self.browser.is_alive():
                    return
                    
                frames = self.browser.get_all_frames()
                for path, identifier in frames:
                    indent = "  " * path.count('/')
                    self.combo_frames.addItem(f"{indent}📄 {identifier}", path)
                if manual_target and self.combo_frames.findData(manual_target) < 0:
                    manual_target = None
                    self._frame_selection_explicit = False
                target_frame = manual_target
                if not target_frame:
                    item = self._get_current_item()
                    item_frame = item.found_frame if item is not None else ""
                    if item_frame and self.combo_frames.findData(item_frame) >= 0:
                        target_frame = item_frame
                    elif self.browser.current_frame_path and self.combo_frames.findData(self.browser.current_frame_path) >= 0:
                        target_frame = self.browser.current_frame_path
                    else:
                        target_frame = "main"
                self._set_frame_combo_path(target_frame, explicit=getattr(self, "_frame_selection_explicit", False))
                self._show_toast(f"{len(frames)}개의 프레임을 찾았습니다.", "info")
            finally:
                self.combo_frames.blockSignals(False)

    def _test_xpath(self):
        """XPath 단일 테스트"""
        xpath = self.input_xpath.toPlainText().strip()
        if not xpath: return
        
        if not self.browser.is_alive():
            self._show_toast("브라우저가 연결되지 않았습니다.", "error")
            return
            
        self._show_toast("XPath 검색 중...", "info")
        
        original_frame = self.browser.current_frame_path

        target_frame = self._resolve_active_frame_path()

        try:
            result = self._validate_xpath_for_ui(xpath, target_frame)
            success = bool(result.get('found'))
            name = self.input_name.text().strip()
            self._record_validation_outcome(name, xpath, success, result)
            
            if success:
                msg = f"✅ 발견! (개수: {result.get('count', 1)})"
                detail = f"태그: {result.get('tag')}\n텍스트: {result.get('text')}\n프레임: {result.get('frame_path')}"
                self.txt_result.setPlainText(msg + "\n" + detail)
                self._show_toast("요소를 찾았습니다!", "success")
                
                # 하이라이트
                if result.get('frame_path'):
                    self.browser.highlight(xpath, frame_path=result['frame_path'])
                else:
                    self.browser.highlight(xpath)
            else:
                error_msg = str(result.get('msg') or getattr(self.browser, "last_error", "") or "요소를 찾을 수 없습니다.")
                self.txt_result.setPlainText(f"❌ 실패\n{error_msg}")
                self._show_toast(error_msg, "error")
            self._refresh_table()
        finally:
            # 프레임 복구 (항상 원복)
            try:
                self.browser.switch_to_frame_by_path(original_frame if original_frame else "main")
            except Exception:
                pass

    def _highlight_xpath(self):
        """현재 XPath 하이라이트"""
        xpath = self.input_xpath.toPlainText().strip()
        if not xpath:
            return
        if not self.browser.is_alive():
            self._show_toast("브라우저가 연결되지 않았습니다.", "warning")
            return
        frame_path = self._resolve_active_frame_path()
        if not self.browser.highlight(xpath, frame_path=frame_path):
            last_error = getattr(self.browser, "last_error", "")
            self._show_toast(last_error or "하이라이트 실패", "error")

    def _start_picker(self):
        """요소 선택기 시작"""
        if not self.browser.is_alive():
            self._show_toast("브라우저를 먼저 실행해주세요.", "warning")
            return

        if self.picker_watcher and self.picker_watcher.isRunning():
            self._show_toast("요소 선택 모드가 이미 실행 중입니다.", "info")
            return

        watcher = PickerWatcher(self.browser)
        self.picker_watcher = watcher
        watcher.picked.connect(self._on_picked)
        watcher.cancelled.connect(self._on_pick_cancelled)
        
        self.browser.start_picker(overlay_mode=self.chk_overlay.isChecked())
        watcher.start()
        self._set_picker_action_enabled(True)

        self._show_toast(
            "요소 선택 모드 시작: 브라우저에서 요소에 마우스를 올린 뒤 '현재 요소 고정' 버튼을 누르세요. (ESC: 취소)",
            "info",
            6000,
        )

    def _force_lock_picker(self):
        """앱 버튼으로 현재 호버 요소를 강제 고정."""
        if not self.browser.is_alive():
            self._show_toast("브라우저가 연결되지 않았습니다.", "warning")
            return
        if not self.browser.is_picker_active():
            self._show_toast("먼저 '요소 선택 시작'을 실행하세요.", "warning")
            return
        if self.browser.lock_picker_current():
            self._show_toast("현재 요소를 고정했습니다. 브라우저에서 '이 요소 사용'을 눌러 캡처하세요.", "success")
        else:
            self._show_toast("고정할 요소를 찾지 못했습니다. 브라우저에서 대상 요소 위에 마우스를 올려주세요.", "warning")

    def _force_unlock_picker(self):
        """앱 버튼으로 현재 고정을 강제 해제."""
        if not self.browser.is_alive():
            self._show_toast("브라우저가 연결되지 않았습니다.", "warning")
            return
        if self.browser.unlock_picker_current():
            self._show_toast("요소 고정을 해제했습니다.", "info")
        else:
            self._show_toast("해제할 고정 요소가 없습니다.", "info")

    def _on_picked(self, result):
        """요소 선택 완료"""
        self._set_picker_action_enabled(False)
        if self.picker_watcher:
            self.picker_watcher.stop()
            self.picker_watcher.wait(WORKER_WAIT_TIMEOUT)
            self.picker_watcher = None
        
        if not result or not isinstance(result, dict):
            return

        xpath = result.get('xpath', '')
        css = result.get('css', '')
        tag = result.get('tag', '')
        text = result.get('text', '')
        frame = result.get('frame', 'main')
        
        # 에디터 채우기
        self.input_xpath.setPlainText(xpath)
        self.input_css.setText(css)
        self.input_desc.setText(f"선택됨: {tag} ({text[:20]})")
        
        # 결과창 업데이트
        self.txt_result.setPlainText(f"캡처 위치: {frame}\n태그: {tag}\n텍스트: {text}")
        
        self._show_toast("요소 정보가 캡처되었습니다.", "success")
        
        # 이름 자동 제안
        if not self.input_name.text():
            suggested_name = f"ui_{tag}"
            if "login" in text.lower() or "login" in xpath.lower():
                suggested_name = "login_elem"
            self.input_name.setText(suggested_name)
            
        # 히스토리 추가
        self._add_to_history(xpath, css, tag, frame)

    def _on_pick_cancelled(self):
        """요소 선택 취소"""
        self._set_picker_action_enabled(False)
        if self.picker_watcher:
            self.picker_watcher.stop()
            self.picker_watcher.wait(WORKER_WAIT_TIMEOUT)
            self.picker_watcher = None
        self._show_toast("요소 선택이 취소되었습니다.", "warning")

    def _validate_all(self):
        """전체 검증 시작"""
        if not self.config.items:
            self._show_toast("검증할 항목이 없습니다.", "warning")
            return
            
        if not self.browser.is_alive():
            self._show_toast("브라우저 연결 필요", "error")
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # 현재 열린 모든 윈도우 핸들 수집 (워커에 전달용)
        windows = [w['handle'] for w in self.browser.get_windows()]
        
        worker = ValidateWorker(self.browser, self.config.items, windows)
        self.validate_worker = worker
        worker.progress.connect(lambda v, m: (self.progress_bar.setValue(v), self.lbl_status.setText(m)))
        worker.validated.connect(self._on_validated)
        worker.finished.connect(self._on_validate_finished)
        worker.start()

    def _on_validated(self, name, result):
        """개별 검증 결과 처리"""
        item = self.config.get_item(name)
        if not item:
            return
        self._record_validation_outcome(name, item.xpath, bool(result.get('found')), result)

    def _record_validation_outcome(self, name: str, xpath: str, success: bool, result: Dict[str, Any]):
        """단일/전체/배치 검증 결과 공통 처리."""
        item = self.config.get_item(name)
        if not item:
            return

        item.is_verified = success
        item.record_test(success)

        frame_path = (result or {}).get('frame_path', '') or ''
        if success:
            item.element_tag = (result or {}).get('tag', '') or item.element_tag
            item.found_frame = frame_path or item.found_frame
            current_item = self._get_current_item()
            if (
                current_item is not None
                and current_item.name == item.name
                and not getattr(self, "_frame_selection_explicit", False)
                and frame_path
            ):
                self._set_frame_combo_path(frame_path, explicit=False)

        if self.stats_manager:
            self.stats_manager.record_test(
                name,
                xpath,
                success,
                frame_path=frame_path,
                error_msg=(result or {}).get('msg', '') if not success else "",
            )

        if not success:
            if self.table_model is not None:
                self.table_model.notify_item_changed(name)
            return

        has_snapshot = False
        if self.diff_analyzer and hasattr(self.diff_analyzer, "has_snapshot"):
            has_snapshot = bool(self.diff_analyzer.has_snapshot(name))
        need_snapshot = (not has_snapshot) or not bool(item.element_attributes)

        try:
            info = self.browser.get_element_info(
                xpath,
                frame_path=frame_path,
                include_attributes=need_snapshot,
            )
        except TypeError:
            # 구 시그니처 호환
            info = self.browser.get_element_info(xpath, frame_path=frame_path)
        except Exception:
            info = None

        if not info or not info.get('found'):
            if self.table_model is not None:
                self.table_model.notify_item_changed(name)
            return

        item.element_tag = info.get('tag', item.element_tag) or item.element_tag
        item.found_frame = info.get('frame_path', frame_path or item.found_frame) or item.found_frame

        attrs = info.get('attributes', {})
        if need_snapshot and isinstance(attrs, dict):
            item.element_attributes = dict(attrs)
            snapshot_payload = {
                'xpath': xpath,
                'tag': info.get('tag', ''),
                'id': info.get('id', ''),
                'class': info.get('class', ''),
                'text': info.get('text', ''),
                'attributes': item.element_attributes,
            }
            if self.diff_analyzer and hasattr(self.diff_analyzer, "save_snapshot"):
                self.diff_analyzer.save_snapshot(name, snapshot_payload)

        if self.table_model is not None:
            self.table_model.notify_item_changed(name)

    def _on_validate_finished(self, found, total):
        """검증 완료"""
        self.progress_bar.setVisible(False)
        self._refresh_table()
        self._show_toast(f"검증 완료: {found}/{total} 성공", "success" if found==total else "warning")
        self.validate_worker = None

    def _on_xpath_text_changed(self):
        """XPath 입력 변경 시 실시간 미리보기 타이머 시작"""
        self._live_preview_timer.start()

    def _update_live_preview(self):
        """실시간 매칭 요소 수 업데이트 (비동기)"""
        with perf_span("ui.update_live_preview"):
            xpath = self.input_xpath.toPlainText().strip()
        
            if not xpath:
                self.lbl_live_preview.setText("🔍 매칭: -")
                self.lbl_live_preview.setStyleSheet("color: #6c7086; font-size: 11px;")
                return
            
            if not self.browser.is_alive():
                self.lbl_live_preview.setText("🔍 매칭: (브라우저 없음)")
                self.lbl_live_preview.setStyleSheet("color: #6c7086; font-size: 11px;")
                return

            self._live_preview_request_id += 1
            request_id = self._live_preview_request_id

            if self.live_preview_worker and self.live_preview_worker.isRunning():
                self.live_preview_worker.cancel()

            self.lbl_live_preview.setText("🔍 매칭: 계산 중...")
            self.lbl_live_preview.setStyleSheet("color: #89b4fa; font-size: 11px;")

            worker = LivePreviewWorker(self.browser, xpath, request_id, frame_path=self._resolve_active_frame_path())
            worker.counted.connect(self._on_live_preview_counted)
            worker.failed.connect(self._on_live_preview_failed)
            worker.finished.connect(lambda w=worker: self._on_live_preview_worker_finished(w))
            self.live_preview_worker = worker
            worker.start()

    def _on_live_preview_counted(self, request_id: int, count: int):
        if request_id != self._live_preview_request_id:
            return

        if count < 0:
            self._set_live_preview_error(getattr(self.browser, "last_error", ""))
        elif count == 0:
            self.lbl_live_preview.setText("❌ 매칭: 0개")
            self.lbl_live_preview.setToolTip("")
            self.lbl_live_preview.setStyleSheet("color: #f38ba8; font-size: 11px;")
        elif count == 1:
            self.lbl_live_preview.setText("✅ 매칭: 1개")
            self.lbl_live_preview.setToolTip("")
            self.lbl_live_preview.setStyleSheet("color: #a6e3a1; font-size: 11px;")
        else:
            self.lbl_live_preview.setText(f"🔍 매칭: {count}개")
            self.lbl_live_preview.setToolTip("")
            self.lbl_live_preview.setStyleSheet("color: #fab387; font-size: 11px;")

    def _on_live_preview_failed(self, request_id: int, _error: str):
        if request_id != self._live_preview_request_id:
            return
        last_error = getattr(self.browser, "last_error", "") or _error
        self._set_live_preview_error(last_error)

    def _on_live_preview_worker_finished(self, worker):
        if self.live_preview_worker is worker:
            self.live_preview_worker = None

    def _screenshot_current_element(self):
        """현재 선택된 요소 스크린샷 저장"""
        xpath = self.input_xpath.toPlainText().strip()
        
        if not xpath:
            self._show_toast("XPath를 먼저 입력하세요.", "warning")
            return
        
        if not self.browser.is_alive():
            self._show_toast("브라우저를 먼저 연결하세요.", "warning")
            return
        
        # 저장 경로 선택
        fname, _ = QFileDialog.getSaveFileName(
            cast(QWidget, self), "스크린샷 저장", "element_screenshot.png", "PNG 파일 (*.png)"
        )
        
        if not fname:
            return
        
        # 스크린샷 저장
        frame_path = self._resolve_active_frame_path()
        success = self.browser.screenshot_element(xpath, fname, frame_path=frame_path)

        if success:
            self._show_toast(f"스크린샷 저장 완료: {fname}", "success")
            
            # 현재 항목에 스크린샷 경로 저장
            name = self.input_name.text().strip()
            item = self.config.get_item(name)
            if item:
                item.screenshot_path = fname
        else:
            last_error = getattr(self.browser, "last_error", "")
            self._show_toast(last_error or "스크린샷 저장 실패", "error")

    def _export_dom_selenium_htm(self):
        """현재 Selenium 브라우저의 전체 DOM을 단일 HTM으로 저장."""
        if not self.browser.is_alive():
            self._show_toast("브라우저를 먼저 연결하세요.", "warning")
            return

        default_name = f"selenium_dom_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.htm"
        fname, _ = QFileDialog.getSaveFileName(
            cast(QWidget, self),
            "DOM 저장",
            default_name,
            "HTM 파일 (*.htm *.html)",
        )
        if not fname:
            return

        if not fname.lower().endswith((".htm", ".html")):
            fname += ".htm"

        self._show_toast("DOM 추출 중...", "info", 2000)
        try:
            snapshots = self.browser.collect_dom_snapshots(include_frames=True)
            report = render_dom_report_htm(snapshots, source_label="Selenium")
            with open(fname, "w", encoding="utf-8") as f:
                f.write(report)

            fail_count = sum(1 for s in snapshots if s.error)
            self._show_toast(
                f"DOM 저장 완료: {fname} (문서 {len(snapshots)}개, 실패 {fail_count}개)",
                "success",
                5000,
            )
        except Exception as e:
            logger.error(f"Selenium DOM 저장 실패: {e}")
            self._show_toast(f"DOM 저장 실패: {e}", "error")

