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


class ExplorerInspectionToolsMixin:
    @staticmethod
    def _md_value(value: Any) -> str:
        text = str(value if value is not None else "")
        return text.replace("|", "\\|").replace("\r\n", "<br>").replace("\n", "<br>")

    def _render_feature_diagnostics_markdown(self) -> str:
        """현재 기능/문맥 상태를 Markdown 리포트로 렌더링."""
        lines = [
            "# XPath Explorer 기능 진단 리포트",
            "",
            f"- 생성 시각: {datetime.now().isoformat(timespec='seconds')}",
            f"- 설정 이름: {self._md_value(getattr(getattr(self, 'config', None), 'name', ''))}",
            f"- 저장 항목 수: {len(getattr(getattr(self, 'config', None), 'items', []) or [])}",
            "",
            "## Selenium 상태",
        ]

        browser = getattr(self, "browser", None)
        selenium_alive = False
        if browser is not None:
            try:
                selenium_alive = bool(browser.is_alive())
            except Exception:
                selenium_alive = False
        lines.append(f"- 연결: {'예' if selenium_alive else '아니오'}")
        if browser is not None:
            try:
                meta = browser.get_current_window_metadata()
            except Exception:
                meta = {}
            if isinstance(meta, dict):
                lines.extend([
                    f"- 현재 창 핸들: {self._md_value(meta.get('handle', ''))}",
                    f"- 현재 창 제목: {self._md_value(meta.get('title', ''))}",
                    f"- 현재 URL: {self._md_value(meta.get('url', ''))}",
                ])
            lines.append(f"- 현재 프레임: {self._md_value(getattr(browser, 'current_frame_path', '') or 'main')}")

        combo_windows = getattr(self, "combo_windows", None)
        combo_frames = getattr(self, "combo_frames", None)
        if combo_windows is not None:
            lines.append(f"- UI 선택 창: {self._md_value(combo_windows.currentText())}")
        if combo_frames is not None:
            lines.append(f"- UI 선택 프레임: {self._md_value(combo_frames.currentText())}")

        lines.extend(["", "## Playwright 상태"])
        pw_manager = getattr(self, "pw_manager", None)
        pw_alive = False
        if pw_manager is not None:
            try:
                pw_alive = bool(pw_manager.is_alive())
            except Exception:
                pw_alive = False
        lines.append(f"- 연결: {'예' if pw_alive else '아니오'}")
        if pw_manager is not None:
            try:
                meta = pw_manager.get_current_window_metadata()
            except Exception:
                meta = {}
            if isinstance(meta, dict):
                lines.extend([
                    f"- 현재 창 핸들: {self._md_value(meta.get('handle', ''))}",
                    f"- 현재 창 제목: {self._md_value(meta.get('title', ''))}",
                    f"- 현재 URL: {self._md_value(meta.get('url', ''))}",
                ])
            current_frame = getattr(pw_manager, "_current_frame", None)
            frame_label = ""
            if current_frame is not None:
                frame_label = str(getattr(current_frame, "name", "") or getattr(current_frame, "url", "") or "")
            lines.append(f"- 현재 프레임: {self._md_value(frame_label or 'main')}")

        lines.extend(["", "## 저장 항목 문맥", "|이름|창|URL|프레임|검증|", "|---|---|---|---|---|"])
        items = list(getattr(getattr(self, "config", None), "items", []) or [])
        if items:
            for item in items[:100]:
                lines.append(
                    "|"
                    + "|".join(
                        [
                            self._md_value(getattr(item, "name", "")),
                            self._md_value(getattr(item, "found_window_title", "") or getattr(item, "found_window", "")),
                            self._md_value(getattr(item, "found_window_url", "")),
                            self._md_value(getattr(item, "found_frame", "")),
                            "성공" if bool(getattr(item, "is_verified", False)) else "미검증/실패",
                        ]
                    )
                    + "|"
                )
        else:
            lines.append("|-|-|-|-|-|")

        lines.extend(["", "## 최근 검증 실패", "|시각|항목|프레임|오류|", "|---|---|---|---|"])
        recent_failures: List[Any] = []
        stats_manager = getattr(self, "stats_manager", None)
        if stats_manager is not None and hasattr(stats_manager, "get_recent_history"):
            try:
                recent_failures = [row for row in stats_manager.get_recent_history(50) if not bool(getattr(row, "success", False))][:20]
            except Exception:
                recent_failures = []
        if recent_failures:
            for row in recent_failures:
                lines.append(
                    "|"
                    + "|".join(
                        [
                            self._md_value(getattr(row, "timestamp", "")),
                            self._md_value(getattr(row, "item_name", "")),
                            self._md_value(getattr(row, "frame_path", "")),
                            self._md_value(getattr(row, "error_msg", "")),
                        ]
                    )
                    + "|"
                )
        else:
            lines.append("|-|-|-|-|")

        lines.extend(["", "## Telemetry 요약"])
        try:
            telemetry = error_telemetry.get_summary(top_n=10)
        except Exception:
            telemetry = {}
        lines.extend([
            f"- 총 에러: {telemetry.get('total_errors', 0)}",
            f"- 치명적 에러: {telemetry.get('critical_count', 0)}",
            f"- 최근 버퍼 이벤트: {telemetry.get('buffered_events', 0)}",
        ])
        top_errors = telemetry.get("top_errors", [])
        if top_errors:
            lines.extend(["", "|모듈|함수|메시지|횟수|", "|---|---|---|---|"])
            for row in top_errors:
                lines.append(
                    "|"
                    + "|".join(
                        [
                            self._md_value(row.get("module", "")),
                            self._md_value(row.get("function", "")),
                            self._md_value(row.get("message", "")),
                            self._md_value(row.get("count", 0)),
                        ]
                    )
                    + "|"
                )
        return "\n".join(lines) + "\n"

    def _save_feature_diagnostics_report(self):
        default_name = f"feature_diagnostics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        fname, _ = QFileDialog.getSaveFileName(
            self,
            "기능 진단 리포트 저장",
            default_name,
            "Markdown 파일 (*.md)",
        )
        if not fname:
            return
        if not fname.lower().endswith(".md"):
            fname += ".md"
        try:
            with open(fname, "w", encoding="utf-8") as f:
                f.write(self._render_feature_diagnostics_markdown())
            self._show_toast(f"진단 리포트 저장 완료: {fname}", "success", 4000)
        except Exception as e:
            self._show_toast(f"진단 리포트 저장 실패: {e}", "error")

    def _show_network_analyzer(self):
        """네트워크 분석 다이얼로그"""
        try:
            from xpath_explorer.browser.playwright import NetworkAnalyzer
        except ImportError:
            self._show_toast("Playwright 모듈을 찾을 수 없습니다.", "error")
            return
        
        analyzer = NetworkAnalyzer()
        if not analyzer.is_playwright_available():
            QMessageBox.warning(
                self, "Playwright 필요",
                "네트워크 분석 기능을 사용하려면 Playwright가 필요합니다.\n\n"
                "설치 방법:\n"
                "pip install playwright\n"
                "playwright install chromium"
            )
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("🌐 네트워크 분석")
        dialog.resize(900, 600)
        
        layout = QVBoxLayout(dialog)
        
        # 상태 및 컨트롤
        ctrl_layout = QHBoxLayout()
        
        lbl_status = QLabel("● 대기 중")
        ctrl_layout.addWidget(lbl_status)
        
        input_url = QLineEdit()
        input_url.setPlaceholderText("분석할 URL 입력...")
        input_url.setText(self.config.url or "https://")
        ctrl_layout.addWidget(input_url, 2)
        
        btn_start = QPushButton("🚀 캡처 시작")
        btn_stop = QPushButton("⏹ 중지")
        btn_stop.setEnabled(False)
        
        ctrl_layout.addWidget(btn_start)
        ctrl_layout.addWidget(btn_stop)
        
        layout.addLayout(ctrl_layout)
        
        # 결과 테이블
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["Method", "Status", "Type", "Size", "URL"])
        network_hh = table.horizontalHeader()
        if network_hh is not None:
            network_hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(table)
        
        # 이벤트 핸들러
        def start_capture():
            url = input_url.text().strip()
            if not url:
                return
            
            lbl_status.setText("● 브라우저 시작 중...")
            
            if analyzer.start_browser(url, headless=False):
                analyzer.start_capture()
                lbl_status.setText("● 캡처 중... (페이지 조작 후 중지)")
                lbl_status.setStyleSheet("color: #a6e3a1;")
                btn_start.setEnabled(False)
                btn_stop.setEnabled(True)
            else:
                last_error = getattr(analyzer, "last_error", "")
                if last_error:
                    lbl_status.setText(f"● 시작 실패: {last_error}")
                    self._show_toast(f"네트워크 분석기 시작 실패: {last_error}", "error")
                else:
                    lbl_status.setText("● 시작 실패")
                lbl_status.setStyleSheet("color: #f38ba8;")
        
        def stop_capture():
            requests = analyzer.stop_capture()
            analyzer.close()
            
            lbl_status.setText(f"● 완료 ({len(requests)}개 요청)")
            lbl_status.setStyleSheet("color: #89b4fa;")
            btn_start.setEnabled(True)
            btn_stop.setEnabled(False)
            
            # 테이블 채우기
            table.setRowCount(0)
            for req in requests:
                row = table.rowCount()
                table.insertRow(row)
                table.setItem(row, 0, QTableWidgetItem(req.method))
                table.setItem(row, 1, QTableWidgetItem(str(req.status)))
                table.setItem(row, 2, QTableWidgetItem(req.resource_type))
                table.setItem(row, 3, QTableWidgetItem(f"{req.response_size}"))
                table.setItem(row, 4, QTableWidgetItem(req.url[:100]))
        
        btn_start.clicked.connect(start_capture)
        btn_stop.clicked.connect(stop_capture)
        
        # 닫기 시 정리
        def on_close():
            analyzer.close()
            dialog.reject()
        
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(on_close)
        layout.addWidget(btn_close)
        
        dialog.exec()

    def _show_statistics(self):
        """통계 대시보드"""
        dialog = QDialog(self)
        dialog.setWindowTitle("📈 테스트 통계")
        dialog.resize(700, 500)
        
        layout = QVBoxLayout(dialog)
        
        # 전체 요약
        summary = self.stats_manager.get_summary()
        summary_text = (
            f"총 항목: {summary['total_items']}개 | "
            f"총 테스트: {summary['total_tests']}회 | "
            f"평균 성공률: {summary['average_success_rate']:.1f}%"
        )
        lbl_summary = QLabel(summary_text)
        lbl_summary.setStyleSheet("font-size: 15px; font-weight: bold; padding: 10px;")
        layout.addWidget(lbl_summary)
        
        # 탭 위젯
        tabs = QTabWidget()
        
        # 탭 1: 항목별 통계
        tab_items = QWidget()
        tab_items_layout = QVBoxLayout(tab_items)
        
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["이름", "총 테스트", "성공", "실패", "성공률"])
        stats_hh = table.horizontalHeader()
        if stats_hh is not None:
            stats_hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        
        for item in self.config.items:
            if item.test_count > 0:
                row = table.rowCount()
                table.insertRow(row)
                table.setItem(row, 0, QTableWidgetItem(item.name))
                table.setItem(row, 1, QTableWidgetItem(str(item.test_count)))
                table.setItem(row, 2, QTableWidgetItem(str(item.success_count)))
                table.setItem(row, 3, QTableWidgetItem(str(item.test_count - item.success_count)))
                
                rate_item = QTableWidgetItem(f"{item.success_rate:.0f}%")
                if item.success_rate >= 80:
                    rate_item.setForeground(QColor("#a6e3a1"))
                elif item.success_rate < 50:
                    rate_item.setForeground(QColor("#f38ba8"))
                table.setItem(row, 4, rate_item)
        
        tab_items_layout.addWidget(table)
        tabs.addTab(tab_items, "항목별 통계")
        
        # 탭 2: 불안정 항목
        tab_unstable = QWidget()
        tab_unstable_layout = QVBoxLayout(tab_unstable)
        
        unstable_items = self.stats_manager.get_unstable_items(80)
        if unstable_items:
            list_unstable = QListWidget()
            for stat in unstable_items:
                list_unstable.addItem(f"❌ {stat.name} - 성공률: {stat.success_rate:.0f}% ({stat.total_tests}회)")
            tab_unstable_layout.addWidget(list_unstable)
        else:
            tab_unstable_layout.addWidget(QLabel("불안정한 항목이 없습니다. 👍"))
        
        tabs.addTab(tab_unstable, "불안정 항목")
        
        layout.addWidget(tabs)
        
        # 버튼
        btn_layout = QHBoxLayout()
        
        btn_clear = QPushButton("🗑 통계 초기화")
        btn_clear.clicked.connect(lambda: (
            self.stats_manager.clear_statistics(),
            self._show_toast("통계가 초기화되었습니다.", "success"),
            dialog.reject()
        ))
        btn_layout.addWidget(btn_clear)
        
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(dialog.reject)
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)
        
        dialog.exec()

    def _show_validation_history_panel(self):
        """최근 검증 결과를 실시간으로 보여주는 히스토리 패널."""
        dialog = QDialog(self)
        dialog.setWindowTitle("🕒 실시간 검증 히스토리")
        dialog.resize(980, 580)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(10)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("상태:"))
        combo_status = QComboBox()
        combo_status.addItem("전체", "all")
        combo_status.addItem("성공만", "success")
        combo_status.addItem("실패만", "failed")
        filter_row.addWidget(combo_status)
        filter_row.addWidget(QLabel("이름 필터:"))
        input_name = QLineEdit()
        input_name.setPlaceholderText("항목명 포함 검색")
        filter_row.addWidget(input_name, 1)
        filter_row.addWidget(QLabel("최대"))
        spin_limit = QSpinBox()
        spin_limit.setMinimum(10)
        spin_limit.setMaximum(500)
        spin_limit.setSingleStep(10)
        spin_limit.setValue(50)
        filter_row.addWidget(spin_limit)
        filter_row.addWidget(QLabel("건"))
        layout.addLayout(filter_row)

        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(["시간", "항목", "XPath", "결과", "프레임", "메시지"])
        table_hh = table.horizontalHeader()
        if table_hh is not None:
            table_hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            table_hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            table_hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
            table_hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
            table_hh.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
            table_hh.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        table_vh = table.verticalHeader()
        if table_vh is not None:
            table_vh.setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(table, 1)

        lbl_summary = QLabel("")
        lbl_summary.setStyleSheet("color: #6c7086;")
        layout.addWidget(lbl_summary)

        def refresh_view():
            records = self.stats_manager.get_recent_history(limit=500)
            status_filter = str(combo_status.currentData() or "all")
            name_filter = input_name.text().strip().lower()
            limit = spin_limit.value()

            filtered = []
            for record in records:
                if status_filter == "success" and not record.success:
                    continue
                if status_filter == "failed" and record.success:
                    continue
                if name_filter and name_filter not in record.item_name.lower():
                    continue
                filtered.append(record)

            filtered = filtered[:limit]
            table.setRowCount(0)
            for record in filtered:
                row = table.rowCount()
                table.insertRow(row)
                table.setItem(row, 0, QTableWidgetItem(record.timestamp[:19]))
                table.setItem(row, 1, QTableWidgetItem(record.item_name))
                xpath_item = QTableWidgetItem(record.xpath)
                xpath_item.setToolTip(record.xpath)
                table.setItem(row, 2, xpath_item)
                status_item = QTableWidgetItem("✅" if record.success else "❌")
                status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row, 3, status_item)
                table.setItem(row, 4, QTableWidgetItem(record.frame_path or "main"))
                table.setItem(row, 5, QTableWidgetItem(record.error_msg or ("Found" if record.success else "")))

            success_count = sum(1 for r in filtered if r.success)
            fail_count = len(filtered) - success_count
            lbl_summary.setText(
                f"표시 {len(filtered)}건 | 성공 {success_count}건 | 실패 {fail_count}건"
            )

        timer = QTimer(dialog)
        timer.setInterval(1000)
        timer.timeout.connect(refresh_view)
        timer.start()

        combo_status.currentIndexChanged.connect(lambda _=None: refresh_view())
        input_name.textChanged.connect(lambda _=None: refresh_view())
        spin_limit.valueChanged.connect(lambda _=None: refresh_view())
        refresh_view()

        btn_row = QHBoxLayout()
        btn_refresh = QPushButton("↻ 새로고침")
        btn_refresh.clicked.connect(refresh_view)
        btn_row.addWidget(btn_refresh)
        btn_row.addStretch()
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(dialog.reject)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

        dialog.exec()

    def _collect_active_dom_snapshots(
        self,
        *,
        include_frames: bool = True,
        scope: str = "all",
    ) -> Tuple[List[Any], str]:
        """현재 활성 브라우저(Selenium/Playwright)의 DOM 스냅샷 수집."""
        if self.browser.is_alive():
            return self.browser.collect_dom_snapshots(include_frames=include_frames, scope=scope), "Selenium"
        if self.pw_manager and self.pw_manager.is_alive():
            return self.pw_manager.collect_dom_snapshots(include_frames=include_frames, scope=scope), "Playwright"
        return [], ""

    def _export_dom_diff_report(self):
        """기준선 대비 현재 DOM 비교 리포트 생성/저장."""
        snapshots, source = self._collect_active_dom_snapshots()
        if not snapshots:
            self._show_toast("활성 브라우저가 없습니다. Selenium 또는 Playwright를 먼저 연결하세요.", "warning")
            return

        baseline = list(getattr(self, "_dom_diff_baseline", []) or [])
        if not baseline:
            self._dom_diff_baseline = list(snapshots)
            self._dom_diff_source = source
            self._show_toast("DOM 기준선을 저장했습니다. 변경 후 다시 실행하면 diff 리포트를 생성합니다.", "success", 3500)
            return

        baseline_source = str(getattr(self, "_dom_diff_source", "") or "")
        if baseline_source and baseline_source != source:
            self._dom_diff_baseline = list(snapshots)
            self._dom_diff_source = source
            self._show_toast(
                f"DOM 기준선 소스가 변경되었습니다 ({baseline_source} -> {source}). 기준선을 재설정했습니다.",
                "warning",
                4500,
            )
            return

        default_name = f"dom_diff_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.htm"
        fname, _ = QFileDialog.getSaveFileName(
            self,
            "DOM 비교 리포트 저장",
            default_name,
            "HTM 파일 (*.htm *.html)",
        )
        if not fname:
            return
        if not fname.lower().endswith((".htm", ".html")):
            fname += ".htm"

        try:
            report = render_dom_diff_report_htm(
                baseline,
                snapshots,
                source_label=f"{source} DOM",
            )
            with open(fname, "w", encoding="utf-8") as f:
                f.write(report)

            changes = diff_dom_snapshots(baseline, snapshots)
            changed_count = len(changes)
            self._dom_diff_baseline = list(snapshots)
            self._dom_diff_source = source
            self._show_toast(
                f"DOM 비교 리포트 저장 완료: {fname} (변경 {changed_count}건)",
                "success",
                5000,
            )
        except Exception as e:
            logger.error(f"DOM 비교 리포트 저장 실패: {e}")
            self._show_toast(f"DOM 비교 리포트 저장 실패: {e}", "error")

    def _show_error_telemetry(self):
        """오류 텔레메트리 대시보드."""
        dialog = QDialog(self)
        dialog.setWindowTitle("🚨 오류 텔레메트리")
        dialog.resize(860, 560)

        layout = QVBoxLayout(dialog)

        lbl_summary = QLabel()
        lbl_summary.setStyleSheet("font-size: 14px; font-weight: bold; padding: 8px;")
        layout.addWidget(lbl_summary)

        tabs = QTabWidget()
        layout.addWidget(tabs, 1)

        tab_top = QWidget()
        top_layout = QVBoxLayout(tab_top)
        table_top = QTableWidget()
        table_top.setColumnCount(4)
        table_top.setHorizontalHeaderLabels(["횟수", "모듈", "함수", "메시지"])
        top_hh = table_top.horizontalHeader()
        if top_hh is not None:
            top_hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            top_hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            top_hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            top_hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        top_layout.addWidget(table_top)
        tabs.addTab(tab_top, "Top 오류")

        tab_recent = QWidget()
        recent_layout = QVBoxLayout(tab_recent)
        table_recent = QTableWidget()
        table_recent.setColumnCount(4)
        table_recent.setHorizontalHeaderLabels(["시간", "레벨", "위치", "메시지"])
        recent_hh = table_recent.horizontalHeader()
        if recent_hh is not None:
            recent_hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            recent_hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            recent_hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            recent_hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        recent_layout.addWidget(table_recent)
        tabs.addTab(tab_recent, "최근 이벤트")

        def refresh_view():
            summary = error_telemetry.get_summary(top_n=30)
            lbl_summary.setText(
                f"누적 오류: {summary['total_errors']}건 | "
                f"치명 오류: {summary['critical_count']}건 | "
                f"고유 오류 유형: {summary['unique_error_types']}개 | "
                f"버퍼 이벤트: {summary['buffered_events']}건"
            )

            table_top.setRowCount(0)
            for row_data in summary["top_errors"]:
                row = table_top.rowCount()
                table_top.insertRow(row)
                table_top.setItem(row, 0, QTableWidgetItem(str(row_data["count"])))
                table_top.setItem(row, 1, QTableWidgetItem(row_data["module"]))
                table_top.setItem(row, 2, QTableWidgetItem(row_data["function"]))
                table_top.setItem(row, 3, QTableWidgetItem(row_data["message"]))

            recent_events = error_telemetry.get_recent_events(limit=200)
            table_recent.setRowCount(0)
            for event in recent_events:
                row = table_recent.rowCount()
                table_recent.insertRow(row)
                location = f"{event.module}.{event.function}:{event.line}"
                table_recent.setItem(row, 0, QTableWidgetItem(event.timestamp_iso))
                table_recent.setItem(row, 1, QTableWidgetItem(event.level))
                table_recent.setItem(row, 2, QTableWidgetItem(location))
                table_recent.setItem(row, 3, QTableWidgetItem(event.message))

        refresh_view()

        btn_layout = QHBoxLayout()

        btn_save = QPushButton("💾 리포트 저장")

        def save_report():
            default_name = f"error_telemetry_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            fname, _ = QFileDialog.getSaveFileName(
                self,
                "오류 텔레메트리 리포트 저장",
                default_name,
                "Markdown 파일 (*.md)",
            )
            if not fname:
                return
            if not fname.lower().endswith(".md"):
                fname += ".md"
            try:
                content = error_telemetry.render_markdown_report(top_n=30, recent_limit=200)
                with open(fname, "w", encoding="utf-8") as f:
                    f.write(content)
                self._show_toast(f"오류 리포트 저장 완료: {fname}", "success")
            except Exception as e:
                logger.error(f"오류 리포트 저장 실패: {e}")
                self._show_toast(f"리포트 저장 실패: {e}", "error")

        btn_save.clicked.connect(save_report)
        btn_layout.addWidget(btn_save)

        btn_clear = QPushButton("🧹 텔레메트리 초기화")

        def clear_telemetry():
            choice = QMessageBox.question(
                dialog,
                "오류 텔레메트리 초기화",
                "수집된 오류 텔레메트리 데이터를 초기화하시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if choice != QMessageBox.StandardButton.Yes:
                return
            error_telemetry.clear()
            refresh_view()
            self._show_toast("오류 텔레메트리가 초기화되었습니다.", "success")

        btn_clear.clicked.connect(clear_telemetry)
        btn_layout.addWidget(btn_clear)

        btn_refresh = QPushButton("↻ 새로고침")
        btn_refresh.clicked.connect(refresh_view)
        btn_layout.addWidget(btn_refresh)

        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(dialog.reject)
        btn_layout.addWidget(btn_close)

        layout.addLayout(btn_layout)
        dialog.exec()

    def _show_diff_analyzer(self):
        """Diff 분석 다이얼로그"""
        if not self.browser.is_alive():
            self._show_toast("브라우저를 먼저 연결하세요.", "warning")
            return
        
        if not self.config.items:
            self._show_toast("분석할 항목이 없습니다.", "warning")
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("🔍 XPath 변경 감지 (Diff 분석)")
        dialog.resize(800, 550)
        
        layout = QVBoxLayout(dialog)
        
        # 분석 버튼
        btn_analyze = QPushButton("🔍 전체 분석 실행")
        btn_analyze.setObjectName("warning")
        btn_analyze.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(btn_analyze)
        
        # 요약 라벨
        lbl_summary = QLabel("분석 버튼을 클릭하여 시작하세요.")
        lbl_summary.setStyleSheet("font-size: 14px; padding: 10px;")
        layout.addWidget(lbl_summary)
        
        # 결과 테이블
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["상태", "항목", "변경 사항", "XPath"])
        diff_hh = table.horizontalHeader()
        if diff_hh is not None:
            diff_hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        table.setColumnWidth(0, 50)
        table.setColumnWidth(1, 120)
        table.setColumnWidth(3, 200)
        diff_vh = table.verticalHeader()
        if diff_vh is not None:
            diff_vh.setVisible(False)
        layout.addWidget(table)
        
        def _render_diff_results(results):
            table.setUpdatesEnabled(False)
            try:
                table.setRowCount(len(results))
                unchanged = modified = missing = 0
                for row, result in enumerate(results):
                    status_item = QTableWidgetItem(result.status_icon)
                    status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    table.setItem(row, 0, status_item)

                    table.setItem(row, 1, QTableWidgetItem(result.item_name))

                    changes_text = ", ".join(result.changes) if result.changes else "-"
                    table.setItem(row, 2, QTableWidgetItem(changes_text))

                    xpath_short = result.xpath[:40] + "..." if len(result.xpath) > 40 else result.xpath
                    xpath_item = QTableWidgetItem(xpath_short)
                    xpath_item.setToolTip(result.xpath)
                    table.setItem(row, 3, xpath_item)

                    if result.status == "unchanged":
                        unchanged += 1
                    elif result.status == "modified":
                        modified += 1
                    elif result.status == "missing":
                        missing += 1
                lbl_summary.setText(f"분석 완료: ✅ 변경없음 {unchanged}개 | ⚠️ 수정됨 {modified}개 | ❌ 찾지못함 {missing}개")
            finally:
                table.setUpdatesEnabled(True)

        def _on_diff_progress(_value, message):
            lbl_summary.setText(message)

        def _on_diff_completed(results):
            btn_analyze.setEnabled(True)
            self.diff_worker = None
            _render_diff_results(results)

        def _on_diff_failed(message):
            btn_analyze.setEnabled(True)
            self.diff_worker = None
            lbl_summary.setText(f"분석 실패: {message}")

        def run_analysis():
            if self.diff_worker and self.diff_worker.isRunning():
                return
            lbl_summary.setText("분석 중...")
            btn_analyze.setEnabled(False)
            self.diff_worker = DiffAnalyzeWorker(list(self.config.items), self.browser, self.diff_analyzer)
            self.diff_worker.progress.connect(_on_diff_progress)
            self.diff_worker.completed.connect(_on_diff_completed)
            self.diff_worker.failed.connect(_on_diff_failed)
            self.diff_worker.start()
        
        btn_analyze.clicked.connect(run_analysis)

        dialog.finished.connect(
            lambda _=None: (
                self.diff_worker.cancel() if self.diff_worker and self.diff_worker.isRunning() else None
            )
        )
        
        # 닫기 버튼
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(dialog.reject)
        layout.addWidget(btn_close)
        
        dialog.exec()
