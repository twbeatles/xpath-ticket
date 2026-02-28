# 🔍 XPath Explorer v4.2

티켓 사이트 및 웹 자동화를 위한 강력한 XPath 요소 탐색, 분석, 관리 도구

## ✨ v4.2 업데이트 (2026.01)

### 🛡️ 보안 및 안정성 강화
- **핵심 수정**: LocalStorage XSS 취약점 해결, 네트워크 리스너 메모리 누수 수정
- **스레드 안정성**: 요소 선택 감시자(PickerWatcher) 스레드 동기화 개선
- **메모리 최적화**: 히스토리 관리 메모리 사용량 최적화
- **견고성 강화**: 프레임 캐시 무효화 로직으로 네비게이션 안정성 확보

### ⚡ 기능 개선
- **프레임 지원**: 프레임 전환(`switch_to_frame`) 기능 구현 완료
- **CSS/XPath**: 특수 문자(따옴표, ID 등) 이스케이프 처리 강화
- **검증 경로**: PDF 저장 시 Headless 모드 검증 로직 추가

### 🧰 안정화 패치 (2026.02)
- **Code Generator Fix**: Selenium/Playwright/PyAutoGUI 코드 생성 시 문자열 포맷 충돌(`KeyError`) 수정
- **Network Analyzer Recovery**: `NetworkAnalyzer` 어댑터 복구 및 응답 크기(`response_size`) 표시 지원
- **History Integrity**: preset/new/open 직후 Undo 기준점 재설정으로 히스토리 오염 방지
- **Validation Data Flow**: 단일/전체/배치 검증 결과를 통합 기록(통계 + Diff 스냅샷)
- **Error Telemetry Dashboard**: 오류 집계/최근 이벤트/Markdown 리포트 저장 기능 추가
- **DOM Export (Selenium/Playwright)**: 창/팝업/iframe 전체 DOM을 단일 `.htm`으로 저장
- **DOM Diff Report**: 기준선 대비 변경 DOM 섹션 강조 리포트 저장 지원
- **XPath Template Library**: 자주 쓰는 XPath 패턴을 카테고리 기반으로 검색/적용
- **Batch Scenario Runner**: JSON 시나리오(검증/대기) 기반 일괄 실행
- **Validation History Panel**: 최근 검증 이력 500건 조회/필터 UI 제공

### 🎨 UI/UX 개선 (v4.1)
- 연결 상태 glow 애니메이션
- 테이블 선택/hover 효과 강화
- 검색창 초기화(X) 버튼
- 빈 상태 안내 메시지

---

## 🤖 AI XPath 어시스턴트
- **OpenAI & Gemini 연동**: 자연어로 XPath 자동 생성
- **멀티 모델 지원**: GPT-5.2, Gemini Flash Latest 등 최신 경량 모델

## 🔄 히스토리 & 안전 장치
- **Undo/Redo**: 기본 50개 히스토리(`HISTORY_MAX_SIZE`, 조정 가능)
- **Diff 분석**: 페이지 변경 감지

## ⚡ 생산성 도구
- 실시간 미리보기
- XPath 최적화
- 요소 스크린샷
- XPath 템플릿 라이브러리
- 배치 시나리오 실행기
- DOM 추출/DOM 비교 리포트

---

## 📦 설치

```bash
# (권장) requirements 사용
pip install -r requirements/requirements-full.txt

# 최소 설치만 원하면
# pip install -r requirements/requirements.txt

# Playwright Chromium 설치 (선택 기능이지만 EXE에서도 동일 기능 사용 시 필요)
python -m playwright install chromium
```

> 네트워크 분석/Playwright 스캔 기능은 Chromium 설치가 되어 있어야 정상 동작합니다.

---

## 🚀 실행

```bash
python "xpath 조사기(모든 티켓 사이트).py"
```

---

## 🔨 빌드 (PyInstaller)

```bash
# UPX 설치 시 경량화 적용 (권장)
pyinstaller packaging/pyinstaller/xpath_explorer.spec
```

빌드 결과: `dist/XPathExplorer_v4.2.exe` (약 50-80MB)

---

## 📁 프로젝트 구조

| 경로 | 설명 |
|------|------|
| `xpath 조사기(모든 티켓 사이트).py` | 레거시 진입점 래퍼 |
| `xpath_explorer/main_window.py` | 메인 윈도우 조합 |
| `xpath_explorer/mixins/` | UI 조립/브라우저 액션/데이터/도구 Mixin |
| `xpath_explorer/core/` | 상수, 설정 모델, 성능 로깅 |
| `xpath_explorer/browser/` | Selenium/Playwright, DOM Export |
| `xpath_explorer/workers/` | 백그라운드 QThread 워커 |
| `xpath_explorer/tools/` | AI, 코드 생성, XPath 최적화 |
| `xpath_explorer/analysis/` | Diff 분석, 검증 통계 |
| `xpath_explorer/state/` | Undo/Redo 히스토리 상태 |
| `xpath_explorer/ui/` | 스타일, 위젯, 테이블 모델/프록시 |
| `docs/` | 운영/분석 문서 (`claude.md`, `gemini.md`, 구조 분석) |
| `requirements/` | 환경별 의존성 목록 |
| `packaging/pyinstaller/` | 배포 스펙 파일 |
| `config/` | 샘플/백업 설정 JSON |
| `archive/` | 과거 스냅샷/레거시 스크립트 보관 |

---

## ⌨️ 단축키

| 단축키 | 기능 |
|--------|------|
| Ctrl+N | 새 항목 |
| Ctrl+S | 저장 |
| Ctrl+Z | 실행 취소 |
| Ctrl+Y | 다시 실행 |
| Ctrl+T | XPath 테스트 |
| Delete | 삭제 |

---

## 📄 라이선스

MIT License

---

## 성능 아키텍처 (v4.2 리팩터링)

- `QTableWidget` 기반 목록 렌더링을 `QTableView + XPathItemTableModel + XPathFilterProxyModel` 구조로 교체했습니다.
- 검색/카테고리/태그/즐겨찾기 필터는 전체 행 재렌더링 대신 프록시 무효화 기반으로 동작합니다.
- Selenium 검증 경로는 재사용 가능한 검증 세션을 지원합니다.
  - `begin_validation_session()`
  - `validate_xpath(xpath, preferred_frame=None, session=None)`
  - `end_validation_session(session)`
- `get_element_info()`는 다음 옵션을 지원합니다.
  - `include_attributes=True|False`
  - `session` 캐시 재사용
- 통계 저장은 비동기 배치 방식으로 동작합니다.
  - `record_test()`는 메모리 상태만 갱신
  - 백그라운드 writer가 주기적으로 flush 수행
  - `save()`는 동기 flush 동작 유지
  - `shutdown(timeout=...)`은 종료 시 flush 후 writer thread 정지
- 성능 지표는 `perf_span`으로 집계되며 앱 종료 시 요약(`count/avg/p95/max`)을 출력합니다.

## 모듈 구조 (v4.2 분할)

- 하위 호환을 위해 레거시 진입점 파일을 유지합니다.
  - `xpath 조사기(모든 티켓 사이트).py`는 새 앱 패키지를 import 후 실행합니다.
- 메인 윈도우 조합 로직:
  - `xpath_explorer/main_window.py`
- 런타임 로거 초기화:
  - `xpath_explorer/runtime.py`
- 기능별 패키지:
  - `xpath_explorer/core/`
  - `xpath_explorer/browser/`
  - `xpath_explorer/workers/`
  - `xpath_explorer/workers/background.py`
  - `xpath_explorer/tools/`
  - `xpath_explorer/analysis/`
  - `xpath_explorer/state/`
  - `xpath_explorer/ui/`
- 기존 단일 클래스 `XPathExplorer` 메서드는 책임별로 분리되었습니다.
  - `xpath_explorer/mixins/ui_mixin.py`
  - `xpath_explorer/mixins/browser_mixin.py`
  - `xpath_explorer/mixins/data_mixin.py`
  - `xpath_explorer/mixins/tools_mixin.py`

호환 정책:
- 기존 실행 명령은 변경하지 않습니다.
- 기존 JSON 스키마와 사용자 UI 라벨 호환성을 유지합니다.

## 문서-코드 정합성 체크

```bash
python scripts/check_docs_sync.py
```

## 테스트 맵 (핵심 회귀 축)

- 브라우저/프레임 복원: `tests/test_browser_frame_hint.py`, `tests/test_selenium_frame_restore.py`
- DOM Export: `tests/test_browser_dom_export.py`, `tests/test_playwright_dom_export.py`, `tests/test_dom_report_renderer.py`
- 배치/워커: `tests/test_batch_worker_cancel.py`, `tests/test_batch_scenario_worker.py`
- Playwright 어댑터: `tests/test_network_analyzer_adapter.py`
- 문서 정합성: `tests/test_docs_sync_check.py`

## 개발 품질 체크 (정합성 + 커버리지)

```bash
python scripts/run_quality_checks.py
```

## 구현 점검 반영 (2026-02-28)

- `IMPLEMENTATION_REVIEW.md`의 실행 계획 항목을 코드에 반영했습니다.
- 핵심 반영:
  - Playwright 초기화 실패 시 부분 생성 리소스 정리
  - 배치 시나리오 워커 실패 시그널/재시도 메타데이터(`attempt`, `retry_count`, `max_attempts`)
  - 시나리오 결과 판정 임계치(100%/80~99%/<80%, cancelled, total=0)
  - 설정 저장/복원(`ui/font_size`, `ui/right_tab_index`, `ui/url_panel_expanded`, `ui/last_preset`)
  - 오류 텔레메트리 Markdown escape 및 로거 파일 핸들러 폴백
  - 종료 시 워커 정리 helper 일원화
- 문서 정합성 체크는 계층형(README/docs/tests)으로 검증합니다.

```bash
python scripts/check_docs_sync.py --strict-warnings
python scripts/run_quality_checks.py --strict-doc-warnings
```

## 배포 스펙 점검 메모

- 현재 배포 스펙 파일은 `packaging/pyinstaller/xpath_explorer.spec`입니다.
- 엔트리포인트는 레거시 래퍼(`xpath 조사기(모든 티켓 사이트).py`)를 사용하고,
  실제 앱 로직은 `xpath_explorer/` 패키지 기준으로 수집됩니다.
- `collect_submodules("xpath_explorer")`를 사용하므로 패키지 분할 구조에 맞게 빌드됩니다.
