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

### 🔒 안정성/배포 강화 (2026.03)
- **Validation Miss Cache 개선**: TTL + 프레임 시그니처 무효화로 오탐 고착 방지
- **Undo/Redo 메타데이터 보존**: `alternatives`, `screenshot_path` 보존 + `element_attributes` 64개 제한
- **저장 경로 폴백**: `Path.home()/.xpath_explorer` 실패 시 TEMP 폴백, 최종 in-memory 동작 보장
- **DOM Diff Source Guard**: Selenium/Playwright 소스 불일치 시 baseline 재설정
- **HiDPI 적용 순서 보정**: `configure_qt_env()`를 `QApplication` 생성 전에 적용
- **Headless Qt 호환성**: `xpath_explorer/qt_compat.py`로 CI/headless import 안전성 확보
- **패키지 엔트리포인트 추가**: `python -m xpath_explorer` 및 PyInstaller package entrypoint 지원
- **Release Smoke 자동화**: spec TLS 회귀, HTTPS smoke, DOM 렌더 smoke, optional import 점검

### 🪟 팝업/DOM 문맥 보강 (2026.04)
- **창 문맥 저장**: `found_window`, `found_window_title`, `found_window_url`를 항목에 저장해 팝업 예매창에서도 동일 창 기준으로 재검증/하이라이트/스크린샷 수행
- **현재 창 DOM 저장**: Selenium/Playwright 모두 `전체 DOM 저장`, `현재 창 DOM 저장`, `현재 창 + iframe DOM 저장` 메뉴 지원
- **DOM 리포트 확장**: `scope`, 선택 창 title/URL, `error_type` 집계(`closed_window`, `closed_page`, `detached_frame` 등) 추가
- **Playwright 활성 페이지 추적**: 새 popup/page를 current page로 추적하고 닫힐 때 자동 fallback
- **시나리오 팝업 제어**: `wait_for_popup`, `switch_latest_popup`, `switch_window_by_title`, `switch_root_window` 액션 추가
- **수동 프레임 새로고침**: 프레임 스캔 UI에서 `get_all_frames(force_refresh=True)`를 사용해 캐시를 강제 갱신

### 🧩 구현 안정화 및 진단 보강 (2026.04.28)
- **XPath 안전 생성 공통화**: `xpath_literal`, `xpath_attr_equals`, `xpath_contains_text` 헬퍼를 추가해 AI fallback, Optimizer, Playwright scan, picker 경로에서 따옴표가 섞인 값도 valid XPath로 생성
- **배치/시나리오 문맥 복구**: 실행 후 기본적으로 원래 창/프레임으로 복구하며, 시나리오 JSON의 `leave_context: true`에서만 마지막 문맥 유지
- **검증 결과 메타데이터 확장**: 배치/시나리오 결과에 `frame_path`, `window_handle`, `window_title`, `window_url`, `tag`, `count`, `error_type` 포함
- **Playwright 스캔 범위 확장**: 현재 프레임, 현재 창 전체 프레임, 모든 팝업/프레임 스캔을 지원하고 scan 결과에 창/프레임 출처 저장
- **진단/내보내기**: 도구 메뉴의 기능 진단 Markdown 리포트 저장과 배치/시나리오 결과 CSV/Markdown 저장 지원
- **설정 호환성**: 설정 JSON에 선택 필드 `schema_version`을 저장하고, 로드 시 오래된/잘못된 타입의 선택 필드를 정규화
- **인코딩 게이트 강화**: `.pytest_tmp`, `htmlcov`는 검사에서 제외하고 Selenium split 파일의 한국어 모지바케 패턴을 감지

### 🎨 UI/UX 개선 (v4.1)
- 연결 상태 glow 애니메이션
- 테이블 선택/hover 효과 강화
- 검색창 초기화(X) 버튼
- 빈 상태 안내 메시지

---

## 🤖 AI XPath 어시스턴트
- **OpenAI & Gemini 연동**: 자연어로 XPath 자동 생성
- **멀티 모델 지원**: 앱 기본 OpenAI 모델 `gpt-5.4`, Gemini Flash Latest 등

## 🔄 히스토리 & 안전 장치
- **Undo/Redo**: 기본 50개 히스토리(`HISTORY_MAX_SIZE`, 조정 가능)
- **Diff 분석**: 페이지 변경 감지

## ⚡ 생산성 도구
- 실시간 미리보기
- XPath 최적화
- 요소 스크린샷
- XPath 템플릿 라이브러리
- 배치 시나리오 실행기
- 배치/시나리오 결과 CSV/Markdown 저장
- 팝업-aware 검증/하이라이트/스크린샷
- 기능 진단 Markdown 리포트
- 현재 창 DOM 추출/DOM 비교 리포트

---

## 📦 설치

```bash
# (권장) repo-local 가상환경
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements/requirements-dev.txt

# 배포/풀 기능 빌드가 필요하면
# .\.venv\Scripts\python.exe -m pip install -r requirements/requirements-full.txt

# 최소 설치만 원하면
# .\.venv\Scripts\python.exe -m pip install -r requirements/requirements.txt

# 개발/품질 점검까지 하려면
# .\.venv\Scripts\python.exe -m pip install -r requirements/requirements-dev.txt

# Playwright Chromium 설치 (선택 기능이지만 EXE에서도 동일 기능 사용 시 필요)
.\.venv\Scripts\python.exe -m playwright install chromium
```

> 네트워크 분석/Playwright 스캔 기능은 Chromium 설치가 되어 있어야 정상 동작합니다.
> `pyrightconfig.json`은 현재 Python 인터프리터 기준으로 동작하며, 외부 GUI/브라우저 패키지 import 진단보다 프로젝트 내부 타입 오류 검출에 집중합니다.

---

## 🚀 실행

```bash
python "xpath 조사기(모든 티켓 사이트).py"

# 패키지 엔트리포인트
python -m xpath_explorer
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
| `xpath_explorer/__main__.py` | 패키지 진입점 (`python -m xpath_explorer`) |
| `xpath_explorer/main_window.py` | 메인 윈도우 조합 |
| `xpath_explorer/qt_compat.py` | headless/CI용 Qt 호환 계층 |
| `xpath_explorer/mixins/` | facade mixin + split partial mixin 패키지 |
| `xpath_explorer/mixins/contracts.py` | split mixin 호스트 Protocol 정의 |
| `xpath_explorer/core/` | facade 상수 + 분리된 constants 모듈, 설정 모델, 성능 로깅 |
| `xpath_explorer/browser/` | facade 브라우저 매니저 + split Selenium/Playwright 구현, DOM Export |
| `xpath_explorer/workers/` | facade 워커 + 개별 QThread 워커 구현 |
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
- 호환 facade와 내부 분할 패키지를 함께 유지합니다.
  - 상수 facade: `xpath_explorer/core/constants.py`
  - 상수 내부 모듈: `xpath_explorer/core/app_constants.py`, `browser_constants.py`, `preset_constants.py`, `template_constants.py`, `runtime_constants.py`, `ui_constants.py`
  - 브라우저 facade: `xpath_explorer/browser/browser.py`, `xpath_explorer/browser/playwright.py`
  - 브라우저 내부 모듈: `xpath_explorer/browser/selenium_*.py`, `xpath_explorer/browser/playwright_*.py`
  - 워커 facade: `xpath_explorer/workers/background.py`
  - 워커 내부 모듈: `xpath_explorer/workers/*_worker.py`, `worker_shared.py`
  - mixin facade: `xpath_explorer/mixins/ui_mixin.py`, `xpath_explorer/mixins/browser_mixin.py`, `xpath_explorer/mixins/data_mixin.py`, `xpath_explorer/mixins/tools_mixin.py`
  - mixin 내부 모듈: `xpath_explorer/mixins/ui/`, `browser/`, `data/`, `tools/`
  - split mixin 계약/patch seam: `xpath_explorer/mixins/contracts.py`, `xpath_explorer/mixins/*/deps.py`
  - 나머지 기능 패키지: `xpath_explorer/tools/`, `analysis/`, `state/`, `ui/`

호환 정책:
- 기존 실행 명령은 변경하지 않습니다.
- 기존 JSON 스키마와 사용자 UI 라벨 호환성을 유지합니다.
- facade 경로를 쓰는 테스트/외부 import는 유지하고, 내부 구현만 세분화합니다.

## 문서-코드 정합성 체크

```bash
python scripts/check_docs_sync.py
```

## Pylance/인코딩 로컬 점검

```bash
python scripts/check_encoding_health.py
python -m pyright -p .
pytest -q
```

`pyright` 실행은 `python -m pyright -p .`를 기준으로 유지합니다.

타입 안정성 규칙:
- Qt 의존 import는 `xpath_explorer/qt_compat.py` 또는 `TYPE_CHECKING` 분리 패턴을 우선 사용합니다.
- headless CI에서도 import 가능한 비GUI 모듈 구조를 유지합니다.

## 테스트 맵 (핵심 회귀 축)

- 브라우저/프레임 복원: `tests/test_browser_frame_hint.py`, `tests/test_selenium_frame_restore.py`
- DOM Export: `tests/test_browser_dom_export.py`, `tests/test_playwright_dom_export.py`, `tests/test_dom_report_renderer.py`
- 배치/워커: `tests/test_batch_worker_cancel.py`, `tests/test_batch_scenario_worker.py`, `tests/test_workers_use_validation_session.py`
- Playwright 어댑터/스캔: `tests/test_network_analyzer_adapter.py`, `tests/test_playwright_scan_context.py`
- XPath 안전 생성/설정/리포트: `tests/test_xpath_safety.py`, `tests/test_config_schema.py`, `tests/test_batch_report_exports.py`, `tests/test_feature_diagnostics.py`
- 문서 정합성: `tests/test_docs_sync_check.py`

## 개발 품질 체크 (정합성 + 커버리지)

```bash
python scripts/run_quality_checks.py
python scripts/run_quality_checks.py --with-pyright
```

- `pytest`는 기본적으로 repo-local temp 경로(`.pytest_tmp/`)를 사용합니다.
- `pytest-cov`가 없으면 `run_quality_checks.py`는 자동으로 plain `pytest`로 폴백합니다.
- 커버리지를 강제로 끄려면 `python scripts/run_quality_checks.py --no-cov`를 사용합니다.

릴리즈 스모크까지 포함:

```bash
python scripts/run_quality_checks.py --strict-doc-warnings --smoke-release
```

단독 스모크 실행:

```bash
python scripts/run_release_smoke_checks.py
```

## CI 품질 게이트

- 워크플로: `.github/workflows/quality.yml`
- 실행 대상: PR, `main`/`master` push
- 고정 순서: `check_encoding_health` -> `pyright`
- GitHub Actions에서는 `pytest`를 실행하지 않습니다.
- 테스트는 로컬 또는 필요 시 수동 실행으로 유지합니다.
## 구현 점검 반영 (2026-03-27)

- 2026-03-27 구현 점검의 실행 계획 항목을 코드에 반영했습니다.
- 핵심 반영:
  - Playwright 초기화 실패 시 부분 생성 리소스 정리
  - 배치 시나리오 워커 실패 시그널/재시도 메타데이터(`attempt`, `retry_count`, `max_attempts`)
  - 시나리오 결과 판정 임계치(100%/80~99%/<80%, cancelled, total=0)
  - 설정 저장/복원(`ui/font_size`, `ui/right_tab_index`, `ui/url_panel_expanded`, `ui/last_preset`)
  - 오류 텔레메트리 Markdown escape 및 로거 파일 핸들러 폴백
  - 종료 시 워커 정리 helper 일원화
  - iframe 공통 resolver 적용으로 단일 테스트/live preview/하이라이트/스크린샷 프레임 기준 통일
  - AI 설정 결과 구조화(`ok/config_saved/storage_source/message`) 및 세션 전용 적용 UX 분리
  - `pytest` repo-local temp(`.pytest_tmp/`) 고정, `run_quality_checks.py`의 `pytest-cov` 자동 폴백과 `--no-cov` 지원
  - Selenium 사용자 액션 실패 시 `last_error` 우선 노출, 프레임 액션 테스트 더블의 Pylance 타입 정합성 정리
- 문서 정합성 체크는 계층형(README/docs/tests)으로 검증합니다.

```bash
python scripts/check_docs_sync.py --strict-warnings
python scripts/run_quality_checks.py --strict-doc-warnings
```

## 구현 점검 반영 (2026-04-14)

- 2026-04-14 구현 점검 기준의 팝업/창 문맥 보강 작업을 코드에 반영했습니다.
- 핵심 반영:
  - 항목 저장 스키마에 `found_window_title`, `found_window_url` 추가
  - 저장된 창 문맥 우선 재검증/하이라이트/스크린샷 경로 적용
  - Selenium/Playwright DOM export 범위 분리(`all`, `current`, `current + iframe`)
  - DOM 리포트에 `scope`, 선택 창 title/URL, `error_type` 요약 추가
  - Playwright 활성 페이지 추적 및 popup/page close fallback
  - 시나리오 워커 popup/window 액션(`wait_for_popup`, `switch_latest_popup`, `switch_window_by_title`, `switch_root_window`) 추가
  - 수동 프레임 스캔에 `force_refresh=True` 적용
  - 관련 회귀 테스트 추가: 창 문맥, current-scope DOM export, popup 시나리오 액션, DOM 리포트 요약

## 구현 점검 반영 (2026-04-28)

- 2026-04-28 구현 점검 기준의 P0-P3 개선과 추가 진단/내보내기 기능을 코드에 반영했습니다.
- 핵심 반영:
  - 공통 XPath literal/attribute builder 도입 및 AI/Optimizer/Playwright/picker 생성 경로 적용
  - Selenium 사용자 노출 메시지와 split 파일 주석/문서 문자열의 한글 모지바케 복구
  - 배치/시나리오 워커 결과 dict 확장과 기본 창/프레임 문맥 복구
  - 시나리오 JSON `leave_context` 선택 옵션 추가
  - Playwright scan 범위 확장 및 `ScannedElement` 창/프레임 문맥 저장
  - 닫힌 Playwright page fallback 직후 `is_alive()` 재검증
  - 기능 진단 Markdown 리포트와 배치/시나리오 CSV/Markdown export 추가
  - 설정 JSON `schema_version` 저장 및 로드 타입 정규화
  - 인코딩 검사 skip 경로/한국어 모지바케 토큰 감지 확장

## 구현 점검 반영 (2026-05-03)

- 2026-05-03 구현 리스크 점검의 개선 항목을 코드와 운영 문서에 반영했습니다.
- 핵심 반영:
  - 전체 검증/live preview의 창·프레임 문맥 복구 보강
  - 설정 JSON 중복 이름/빈 이름/빈 XPath import 거부
  - `XPathItem.source_engine` 추가로 Playwright 스캔 출처 보존
  - 설정/통계/AI 설정 저장을 atomic JSON write 방식으로 전환
  - Playwright page handle을 세션 내 안정적인 `pw-page-N` 형식으로 전환
  - 워커 계층의 Qt import를 `qt_compat` 경유로 정리하고 headless-safe import 테스트 추가
  - CI pytest 추가는 보류하고 로컬 품질 절차(`pytest -q`, `pyright`, docs sync)를 유지
  - 임시 점검 문서는 정리하고 README/docs 운영 문서에 최종 정책만 남김

## 배포 스펙 점검 메모

- 현재 배포 스펙 파일은 `packaging/pyinstaller/xpath_explorer.spec`입니다.
- 엔트리포인트 후보는 레거시 래퍼(`xpath 조사기(모든 티켓 사이트).py`)와 패키지 엔트리포인트(`xpath_explorer/__main__.py`)입니다.
- 실제 앱 로직은 `xpath_explorer/` 패키지 기준으로 수집됩니다.
- `collect_submodules("xpath_explorer")`를 사용하므로 패키지 분할 구조에 맞게 빌드됩니다.
- `xpath_explorer.qt_compat`는 hidden import에 명시되어 headless-safe Qt bootstrap 경로를 유지합니다.
- `xpath_explorer.core.paths`는 `atomic_write_json()`을 포함하므로 hidden import에 명시되어 저장 안정성 경로를 유지합니다.
- `openai`/`google.genai`/`playwright`는 빌드 환경에 설치된 경우에만 `hiddenimports`로 포함됩니다.
- 선택 기능까지 포함한 EXE가 필요하면 `requirements/requirements-full.txt` 설치 후 빌드합니다.
- atomic 저장 중 생성되는 `*.json.bak`, `.*.tmp` 로컬 산출물은 `.gitignore`에서 제외합니다.
