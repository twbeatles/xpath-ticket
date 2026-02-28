# XPath Explorer 프로젝트 구조 심층 분석 및 기능 확장 제안

## 1. 분석 범위와 근거 소스

### 분석 목표
- 본 문서는 `XPath Explorer`의 **현재 코드 기준 실제 구조**를 정리하고, 기능 확장 시 바로 실행 가능한 백로그와 로드맵을 제공합니다.
- 단순 개요가 아니라, 기존 문서와 코드의 차이를 명시해 유지보수 시 오판을 줄이는 것을 목표로 합니다.

### 분석 기준
- 사실 소스 우선순위: **코드 > README > claude.md/gemini.md**
- 분석 대상 시점: 현재 저장소 HEAD 기준(로컬 변경 포함)

### 근거 문서
- [`README.md`](D:/twbeatles-repos/xpath-ticket/README.md)
- [`claude.md`](D:/twbeatles-repos/xpath-ticket/claude.md)
- [`gemini.md`](D:/twbeatles-repos/xpath-ticket/gemini.md)

### 근거 코드(핵심)
- 엔트리포인트: [`xpath 조사기(모든 티켓 사이트).py`](D:/twbeatles-repos/xpath-ticket/xpath 조사기(모든 티켓 사이트).py), [`xpath_explorer/main_window.py`](D:/twbeatles-repos/xpath-ticket/xpath_explorer/main_window.py)
- UI 계층: [`xpath_explorer/mixins/ui_mixin.py`](D:/twbeatles-repos/xpath-ticket/xpath_explorer/mixins/ui_mixin.py), [`xpath_explorer/mixins/browser_mixin.py`](D:/twbeatles-repos/xpath-ticket/xpath_explorer/mixins/browser_mixin.py), [`xpath_explorer/mixins/data_mixin.py`](D:/twbeatles-repos/xpath-ticket/xpath_explorer/mixins/data_mixin.py), [`xpath_explorer/mixins/tools_mixin.py`](D:/twbeatles-repos/xpath-ticket/xpath_explorer/mixins/tools_mixin.py)
- 코어 계층: [`xpath_browser.py`](D:/twbeatles-repos/xpath-ticket/xpath_browser.py), [`xpath_playwright.py`](D:/twbeatles-repos/xpath-ticket/xpath_playwright.py), [`xpath_ai.py`](D:/twbeatles-repos/xpath-ticket/xpath_ai.py), [`xpath_config.py`](D:/twbeatles-repos/xpath-ticket/xpath_config.py), [`xpath_workers.py`](D:/twbeatles-repos/xpath-ticket/xpath_workers.py)
- 신규 DOM Export: [`xpath_dom_export.py`](D:/twbeatles-repos/xpath-ticket/xpath_dom_export.py)
- 테스트: [`tests/`](D:/twbeatles-repos/xpath-ticket/tests)

## 2. 프로젝트 현재 상태 스냅샷

### 실행/배포/테스트 환경 요약
- 언어: Python 3.10+ (실행 환경에서는 3.14도 확인됨)
- GUI: PyQt6
- 브라우저 자동화: Selenium + undetected-chromedriver + Playwright(선택)
- 테스트: pytest (`pytest.ini`에서 `tests/` 고정)
- 배포: PyInstaller (`xpath_explorer.spec`)

### 엔트리포인트 구조(핵심)
- 과거 단일 대형 스크립트 구조에서, 현재는 다음 2단계 구조:
  1. [`xpath 조사기(모든 티켓 사이트).py`](D:/twbeatles-repos/xpath-ticket/xpath 조사기(모든 티켓 사이트).py): 레거시 진입점 래퍼
  2. [`xpath_explorer/main_window.py`](D:/twbeatles-repos/xpath-ticket/xpath_explorer/main_window.py): 실제 앱 조립/실행

### 현재 디렉터리 구조(핵심만)

```text
xpath-ticket/
├─ xpath_explorer/
│  ├─ main_window.py
│  ├─ runtime.py
│  └─ mixins/
│     ├─ ui_mixin.py
│     ├─ browser_mixin.py
│     ├─ data_mixin.py
│     └─ tools_mixin.py
├─ xpath_browser.py
├─ xpath_playwright.py
├─ xpath_ai.py
├─ xpath_config.py
├─ xpath_workers.py
├─ xpath_statistics.py
├─ xpath_diff.py
├─ xpath_optimizer.py
├─ xpath_codegen.py
├─ xpath_table_model.py
├─ xpath_filter_proxy.py
├─ xpath_dom_export.py
├─ tests/
└─ README.md / claude.md / gemini.md
```

### 현재 구조에서 눈에 띄는 특징
- UI 책임이 `main_window + mixins`로 분할되어 변경 범위 추적이 쉬움.
- Selenium과 Playwright가 공존하지만 실제 주 흐름은 Selenium 중심, Playwright는 보조 분석/스캔 도구 성격.
- 모델/프록시(`xpath_table_model.py`, `xpath_filter_proxy.py`)로 테이블 렌더링 성능 개선이 반영됨.
- DOM 추출 기능이 공통 포맷 모듈(`xpath_dom_export.py`)로 추상화됨.

## 3. 런타임 아키텍처 (실행 흐름)

### 실행 흐름

```text
python "xpath 조사기(모든 티켓 사이트).py"
  -> xpath_explorer.main_window.main()
    -> QApplication + XPathExplorer(QMainWindow)
      -> mixins 조합 초기화
      -> BrowserManager / Stats / History / AI / Diff 준비
      -> UI 이벤트 루프 시작
```

### 이벤트-도메인 처리 흐름

```text
UI 액션 (버튼/단축키/메뉴)
  -> Mixin 핸들러
    -> BrowserManager / PlaywrightManager / Worker / Config 호출
      -> 결과 반영 (table_model, toast, 상태바, statistics, diff snapshot)
```

### 주요 비동기/백그라운드 경로
- `QThread` 기반: `PickerWatcher`, `ValidateWorker`, `BatchTestWorker`, `LivePreviewWorker`, `AIGenerateWorker`, `DiffAnalyzeWorker`
- 통계 저장: `StatisticsManager` 내부 background writer thread
- 성능 측정: `perf_span(...)` + 종료 시 `log_perf_summary(...)`

## 4. 모듈별 책임/의존성 맵

### Core 모듈

| 모듈 | 핵심 책임 | 주요 의존 | 비고 |
|---|---|---|---|
| `xpath_browser.py` | Selenium 세션/윈도우/프레임/피커/검증/DOM 수집 | selenium, `xpath_constants` | 팝업 우선, frame context 복원, validation session 캐시 |
| `xpath_playwright.py` | Playwright 브라우저/네트워크/스캔/DOM 수집 | playwright, `xpath_constants` | `NetworkAnalyzer` 어댑터 포함 |
| `xpath_ai.py` | OpenAI/Gemini 기반 XPath 생성/개선/분석 | openai, google-genai | API 키 우선순위 + fallback |
| `xpath_config.py` | `XPathItem`, `SiteConfig` 데이터 모델/직렬화 | dataclasses, `SITE_PRESETS` | 하위호환 로딩 처리 |
| `xpath_workers.py` | UI 비동기 작업 분리 | PyQt6 QThread, Browser/AI/Diff | 취소/진행률/완료 시그널 |
| `xpath_statistics.py` | 테스트 통계 누적/비동기 저장 | json, thread | flush/shutdown 제어 |
| `xpath_diff.py` | 스냅샷 저장/비교/리포트 | dataclass | 변경 감지 정책 명확 |
| `xpath_optimizer.py` | XPath 대안 생성/점수화 | 정규식/문자열 규칙 | 전략별 robustness |
| `xpath_codegen.py` | Selenium/Playwright/PyAutoGUI 코드 생성 | 템플릿 | 문자열 포맷 안정화 반영 |
| `xpath_dom_export.py` | DOM 스냅샷 모델 + HTM 리포트 렌더링 | dataclass, html escape | Selenium/Playwright 공통 출력 |

### UI 모듈 (`xpath_explorer/mixins/*.py`)

| 모듈 | 책임 | 호출하는 코어 계층 |
|---|---|---|
| `ui_mixin.py` | 위젯 생성/배치/메뉴/패널 조립 | 직접 코어 호출 최소화, 핸들러 연결 중심 |
| `browser_mixin.py` | Selenium 연결/창·프레임/검증/피커/스크린샷/DOM 저장 | `BrowserManager`, `ValidateWorker`, `LivePreviewWorker` |
| `data_mixin.py` | CRUD/저장·로드/내보내기/검색·필터/히스토리 UI | `SiteConfig`, `HistoryManager` |
| `tools_mixin.py` | 배치 테스트/코드생성/통계/AI/Diff/Playwright 스캔·DOM 저장 | `PlaywrightManager`, `BatchTestWorker`, `AIGenerateWorker`, `DiffAnalyzeWorker` |

## 5. 데이터 모델 및 상태 흐름

### 핵심 데이터 엔티티

| 엔티티 | 위치 | 목적 |
|---|---|---|
| `XPathItem` | `xpath_config.py` | 단일 XPath 항목의 저장 단위 |
| `SiteConfig` | `xpath_config.py` | 사이트별 항목 컬렉션 + 인덱스 |
| `HistoryState` | `xpath_history.py` | Undo/Redo 상태 스냅샷 |
| `ElementSnapshot` / `DiffResult` | `xpath_diff.py` | 변경 감지 및 상태 표현 |
| `TestRecord` / `ItemStatistics` | `xpath_statistics.py` | 검증 이력/요약 통계 |
| `DomSnapshot` | `xpath_dom_export.py` | DOM 추출 결과의 공통 구조 |

### 상태 갱신 경로(요약)
1. 사용자 편집/피커/AI 적용
2. `SiteConfig` 항목 갱신 + `HistoryManager.push_state(...)`
3. 검증 실행
4. 성공 시 `item.record_test(...)`, 통계 기록, diff 스냅샷 갱신
5. 테이블 모델/프록시 갱신 + UI 피드백(toast/result pane)

### 영속화 경로
- 설정: JSON 파일 저장/로드 (`_save_config`, `_open_config`)
- 통계: `~/.xpath_explorer/statistics.json`
- 로그: `~/.xpath_explorer/debug.log`
- 쿠키: 사용자 선택 경로 JSON
- DOM 리포트: 사용자 선택 경로 HTM

## 6. 브라우저 계층 (Selenium vs Playwright) 구조

| 항목 | Selenium (`BrowserManager`) | Playwright (`PlaywrightManager`) |
|---|---|---|
| 기본 역할 | 메인 자동화/검증/피커 | 보조 스캔/네트워크 분석/대체 자동화 |
| 창/팝업 처리 | `get_windows()` + popup 우선 정렬 | `context.pages` 순회 |
| 프레임 처리 | 경로 기반 전환(`switch_to_frame_by_path`) | frame 객체 기반 (`child_frames`) |
| 검증 중심 API | `validate_xpath`, `get_element_info`, `count_elements` | `validate_xpath`, `scan_elements`, `highlight` |
| 안정성 장치 | invalid session 감지/복구, frame context 복원 | browser/context/page 생존성 체크 |
| DOM 수집 | `collect_dom_snapshots(include_frames=True)` | `collect_dom_snapshots(include_frames=True)` |
| 주 UI 연결 | 상단 브라우저 패널 | 자동 탐색 탭 |

### 현재 판단
- 제품 핵심 작업(검증/피커/저장)은 Selenium이 주도.
- Playwright는 탐지 회피/네트워크/스캔 실험축으로 유지되는 이중 구조.
- 향후 중복 기능 통합 시 “브라우저 추상 계층(인터페이스)” 도입 여지가 큼.

## 7. UI 계층 (main_window + mixins) 구조

### 조합 클래스
- `XPathExplorer(ExplorerToolsMixin, ExplorerDataMixin, ExplorerBrowserMixin, ExplorerUIMixin, QMainWindow)`
- 책임 분리가 명확해 “기능 추가 위치”를 빠르게 특정 가능.

### UI 책임 분해 표

| 계층 | 파일 | 주요 책임 | 변경 시 주의점 |
|---|---|---|---|
| 앱 조립 | `main_window.py` | 서비스 객체 생성, 타이머/모델 연결 | 초기화 순서 의존성 |
| UI 구성 | `ui_mixin.py` | 패널/탭/버튼/메뉴 생성 | 시그널 연결 누락 리스크 |
| 브라우저 액션 | `browser_mixin.py` | Selenium 연동 액션 전반 | 창/프레임 복원 보장 필요 |
| 데이터 액션 | `data_mixin.py` | CRUD/설정/내보내기/컨텍스트 메뉴 | 히스토리 기준점 유지 |
| 도구 액션 | `tools_mixin.py` | AI/Diff/Playwright/배치/통계 | 워커 생명주기 관리 |

### UI 확장 패턴(현재 권장)
1. `ui_mixin.py`에 버튼/메뉴 생성
2. 대응 핸들러를 도메인 성격에 맞는 mixin에 구현
3. 백그라운드 작업은 `xpath_workers.py`로 이동
4. 결과는 toast + model update로 반영

## 8. 테스트 구조와 품질 보증 포인트

### 기능 축별 테스트 재분류

| 기능 축 | 테스트 파일 |
|---|---|
| 브라우저/프레임/복원 | `test_browser_frame_hint.py`, `test_selenium_frame_restore.py`, `test_validation_session_cache.py` |
| 워커/배치/세션 재사용 | `test_workers_use_validation_session.py`, `test_batch_worker_cancel.py`, `test_live_preview_worker.py` |
| 모델/프록시/설정 | `test_table_model_proxy.py`, `test_site_config_index.py`, `test_history_manager.py` |
| 통계/성능 경로 | `test_statistics_async_flush.py` |
| AI 경로 | `test_ai_config_precedence.py`, `test_ai_fallback_escape.py` |
| 코드 생성 | `test_codegen_templates.py` |
| Diff 정책 | `test_diff_snapshot_capture_policy.py` |
| Playwright 어댑터 | `test_network_analyzer_adapter.py` |
| DOM Export | `test_dom_report_renderer.py`, `test_browser_dom_export.py`, `test_playwright_dom_export.py` |

### 품질 보증 포인트
- 단위 테스트 중심으로 “회귀 위험이 큰 경로(프레임, 세션, 워커, 통계 flush)”를 커버.
- UI 통합(E2E) 테스트는 부재하므로, 복합 시나리오는 수동 검증 비중이 큼.
- 문서 업데이트와 테스트 추가가 분리되어 있어 “문서-코드 드리프트”가 쉽게 발생.

## 9. 기존 문서와 실제 코드 간 차이점

### 정합성 점검 결과 (2026-02-25)
- 점검 스크립트: `python scripts/check_docs_sync.py`
- 결과: Errors 0 / Warnings 0
- 본 섹션 표는 과거 불일치와 재발 방지 포인트를 함께 기록한 유지보수 기준입니다.

| 문서 주장 | 실제 코드 | 영향 | 수정 권장 |
|---|---|---|---|
| 메인 애플리케이션이 `xpath 조사기(모든 티켓 사이트).py` 단일 대형 파일 중심 | 현재 파일은 레거시 래퍼, 실제 조립은 `xpath_explorer/main_window.py` + mixins | 신규 기여자가 수정 위치를 잘못 찾음 | README/claude/gemini에 “래퍼 + 패키지 구조”를 기본 설명으로 승격 |
| 프로젝트 구조 표에 핵심 파일만 기재 | 실제로 `xpath_table_model.py`, `xpath_filter_proxy.py`, `xpath_dom_export.py`, `xpath_explorer/`가 핵심 경로 | 성능/신규 기능 이해 누락 | 구조 표를 계층형(core/ui/tests)으로 재작성 |
| Undo/Redo가 “무제한” 강조 | 실제 상수 `HISTORY_MAX_SIZE = 50` 기반 제한 | 사용자 기대치와 실제 동작 불일치 | 문구를 “기본 50, 확장 가능”으로 정정 |
| LOC/파일 책임이 단일 스크립트 기준 | 현재는 mixin 분할로 책임 경계가 달라짐 | 리팩터 논의 시 과거 맥락에 고정됨 | 문서의 LOC/책임 표를 최신 분할 기준으로 재산정 |
| Playwright 설명이 보조 기능 수준으로만 요약 | 현재는 DOM 추출/스캔/네트워크 분석까지 실사용 기능 포함 | 기능 홍보/테스트 범위 누락 | README 기능 섹션에 Playwright 탭 기능 상세 추가 |
| 테스트 범위가 일반 설명 위주 | 실제는 프레임 복원/세션 캐시/DOM export 등 정교한 회귀 테스트가 존재 | 품질수준이 과소평가됨 | README에 테스트 맵 섹션 추가 |
| 문서의 구조 트리에서 `xpath_explorer/` 패키지 분할 업데이트가 일부 문단에만 존재 | 실제 런타임은 패키지 분할이 기본 | 문서 내 일관성 저하 | 상단 구조/실행 섹션부터 패키지 분할을 기본 모델로 통일 |

### 최근 반영 완료 항목
- [x] README의 Undo/Redo 설명을 `HISTORY_MAX_SIZE` 기반으로 정정
- [x] README에 DOM Export/DOM Diff/템플릿 라이브러리/시나리오 실행기/오류 텔레메트리 반영
- [x] README에 테스트 맵 섹션 추가
- [x] `claude.md`, `gemini.md` 상단 구조 설명을 `main_window + mixins` 중심으로 정리

## 10. 기능 확장 제안 백로그 (우선순위 포함)

| 기능명 | 사용자 가치 | 주요 변경 파일 | 구현 난이도 | 리스크 | MVP 수용 기준 |
|---|---|---|---|---|---|
| `[P0] 문서-코드 정합성 체크리스트 자동 생성` | 릴리즈마다 문서 누락 방지 | `README.md`, `claude.md`, `gemini.md`, `tests/` | 중 | 체크 규칙 과잉으로 CI 소음 가능 | 릴리즈 전 스크립트가 핵심 파일 누락/불일치 5종 이상 검출 |
| `[P0] 에러 텔레메트리 요약 리포트` | 장애 재현 시간 단축 | `xpath_explorer/runtime.py`, `xpath_statistics.py`, `xpath_explorer/mixins/tools_mixin.py` | 중 | 개인정보/URL 로그 처리 | UI에서 최근 오류 Top N 및 발생 빈도 조회 가능 |
| `[P0] Selenium 세션/팝업 복구 강화` | 예매 실전 안정성 상승 | `xpath_browser.py`, `tests/test_selenium_frame_restore.py` | 중 | 복구 루프 무한 반복 | 창 닫힘/세션 오류 후 3회 내 복구 또는 명확한 실패 반환 |
| `[P0] 테스트 커버리지 리포트 파이프라인` | 변경 영향 가시화 | `requirements-dev.txt`, `pytest.ini`, CI 스크립트 | 하 | 측정 지표 오해 | 핵심 모듈별 커버리지 리포트 자동 생성 |
| `[P1] 사이트 프리셋 편집기 GUI` | 비개발자도 사이트 온보딩 가능 | `xpath_constants.py`, `xpath_explorer/mixins/data_mixin.py`, `xpath_config.py` | 상 | 프리셋 스키마 파손 | 앱 내에서 프리셋 생성/수정/저장/검증 가능 |
| `[P1] XPath 템플릿 라이브러리` | 반복 패턴 재사용으로 작성 시간 절감 | `xpath_codegen.py`, `xpath_explorer/mixins/tools_mixin.py`, `xpath_constants.py` | 중 | 템플릿 품질 편차 | 카테고리별 템플릿 20개 이상 제공 + 클릭 적용 |
| `[P1] 배치 시나리오 실행기` | “단순 개별 테스트”를 “업무 시퀀스 검증”으로 확장 | `xpath_workers.py`, `xpath_explorer/mixins/tools_mixin.py`, `xpath_config.py` | 상 | 시나리오 DSL 설계 복잡도 | 시나리오 JSON 1개 실행으로 다단계 검증 리포트 생성 |
| `[P1] DOM 비교 리포트 확장` | 변경 원인 파악 속도 향상 | `xpath_dom_export.py`, `xpath_diff.py`, `xpath_explorer/mixins/tools_mixin.py` | 중 | 대용량 HTML 처리 비용 | 이전/현재 DOM diff 요약(추가/삭제/변경) 표시 |
| `[P1] 실시간 검증 결과 히스토리 패널` | 디버깅 시 문맥 보존 | `xpath_explorer/mixins/browser_mixin.py`, `xpath_statistics.py`, `xpath_table_model.py` | 중 | UI 복잡도 증가 | 최근 50건 검증 결과를 필터/정렬해서 확인 가능 |
| `[P1] 다중 프로젝트 워크스페이스` | 사이트별 설정 분리 운영 편의 | `xpath_config.py`, `xpath_explorer/mixins/data_mixin.py`, `xpath_constants.py` | 중 | 기존 경로 호환성 | 프로젝트 전환/최근 목록/기본 프로젝트 지정 지원 |
| `[P2] 플러그인형 사이트 어댑터` | 사이트별 커스텀 로직 확장성 확보 | 신규 `plugins/`, `xpath_browser.py`, `xpath_explorer/main_window.py` | 상 | API 안정성 설계 난이도 | 플러그인 1개(샘플) 로드/활성/비활성 가능 |
| `[P2] 규칙 기반 자동 복구 엔진` | XPath 깨짐 자동 대응 | `xpath_optimizer.py`, `xpath_diff.py`, `xpath_ai.py`, `xpath_browser.py` | 상 | 잘못된 자동 수정 위험 | 실패 XPath에 대해 후보 대안 제시 + 사용자 승인 후 반영 |
| `[P2] 레코딩-리플레이 고도화` | 현장 작업 자동화 정확도 향상 | `xpath_playwright.py`, `xpath_workers.py`, `xpath_explorer/mixins/tools_mixin.py` | 상 | 브라우저별 동작 차이 | 클릭/입력/대기 이벤트 기록 후 재실행 성공률 80% 이상 |
| `[P2] 협업용 설정 번들(Import/Export pack)` | 팀 간 설정 공유 효율 향상 | `xpath_config.py`, `xpath_explorer/mixins/data_mixin.py`, `xpath_statistics.py` | 중 | 스키마 버전 충돌 | 단일 번들로 설정+통계+스크린샷 경로 매핑 내보내기 |

## 11. 단계별 실행 로드맵 (P0/P1/P2)

### Sprint 1-2 (P0: 안정성/관찰성/문서 정합성)
- 목표
  - 문서-코드 정합성 자동 점검 도입
  - 세션/창 복구 실패 케이스 축소
  - 오류 관측 가능성 확보
- 산출물
  - 정합성 체크 스크립트 + 문서 업데이트 PR 템플릿
  - 에러 요약 UI 또는 로그 리포트
  - 복구 경로 회귀 테스트 추가

### Sprint 3-5 (P1: 사용자 생산성 기능)
- 목표
  - 비개발자도 설정과 검증 시나리오를 관리
  - 반복 작업을 템플릿/시나리오로 추상화
- 산출물
  - 프리셋 편집기 GUI
  - XPath 템플릿 라이브러리
  - 배치 시나리오 실행기
  - DOM 비교 리포트 확장

### Sprint 6+ (P2: 고급 확장/플러그인성)
- 목표
  - 프로젝트를 “개별 도구”에서 “확장 가능한 플랫폼”으로 전환
- 산출물
  - 플러그인 어댑터 프로토콜
  - 자동 복구 엔진(권장안 + 승인 워크플로우)
  - 레코딩-리플레이 고도화
  - 협업 번들 포맷

## 12. 리스크/가드레일/검증 체크리스트

### 절대 깨면 안 되는 호환성
- 실행 진입점 호환: `python "xpath 조사기(모든 티켓 사이트).py"` 유지
- JSON 스키마 호환: 기존 설정 파일 로드 실패 금지
- UI 핵심 워크플로우 유지: 브라우저 연결 → XPath 테스트 → 저장 루프 유지

### 주요 리스크
- Selenium/Playwright 이원화로 기능 중복/동작 불일치 발생 가능
- mixin 간 결합 증가 시 변경 영향 추적 난이도 상승
- 문서와 코드의 릴리즈 동기화 누락 시 온보딩 비용 급증

### 릴리즈 전 체크리스트
- `tests/` 핵심 회귀 세트 통과(브라우저/프레임/DOM export 포함)
- 문서-코드 불일치 표 갱신
- 설정/통계 파일 backward compatibility 확인
- 브라우저 종료/워커 종료 시 리소스 정리 확인
- 신규 기능의 실패 경로에서 toast + 로그가 명확한지 확인

## 13. 빠른 시작 가이드 (다음 작업 순서)

### 실무 적용 순서
1. 이슈 정의
   - 사용자 시나리오/성공 기준/비기능 요구사항(성능, 안정성)을 1페이지로 명확화
2. 모듈 영향 분석
   - `main_window + 해당 mixin + core 모듈 + tests` 순으로 영향 파일 식별
3. 테스트 추가
   - 변경 로직보다 먼저 실패 재현 테스트 작성(회귀 포인트 우선)
4. UI 반영
   - `ui_mixin`에 진입점 추가 후 해당 mixin에 핸들러 구현
5. 도메인 로직 구현
   - core 모듈에 순수 로직 추가, UI는 orchestration만 유지
6. 문서 업데이트
   - README 기능 요약 + 본 문서의 불일치 표/백로그 상태 갱신
7. 릴리즈 검증
   - 핵심 회귀 테스트 + 수동 시나리오(브라우저 연결, 프레임, 팝업, 저장) 확인

### 다음 1개 작업 추천
- P0 첫 작업으로 **문서-코드 정합성 체크리스트 자동 생성**을 착수하는 것이 가장 효과적입니다.
  - 이유: 이후 모든 기능 확장의 품질 하한선을 고정할 수 있음.

---

## 2026-02-28 정합성 업데이트

### 현재 기준 경로
- 실행 진입점: `xpath 조사기(모든 티켓 사이트).py`
- 메인 윈도우: `xpath_explorer/main_window.py`
- 브라우저 계층: `xpath_explorer/browser/browser.py`, `xpath_explorer/browser/playwright.py`
- 워커 계층: `xpath_explorer/workers/background.py`
- 도구 계층: `xpath_explorer/tools/ai.py`, `xpath_explorer/tools/codegen.py`, `xpath_explorer/tools/optimizer.py`
- 분석 계층: `xpath_explorer/analysis/diff.py`, `xpath_explorer/analysis/statistics.py`
- 상태 계층: `xpath_explorer/state/history.py`
- UI 계층: `xpath_explorer/ui/widgets.py`, `xpath_explorer/ui/table_model.py`, `xpath_explorer/ui/filter_proxy.py`, `xpath_explorer/ui/styles.py`

### 빌드 스펙
- 위치: `packaging/pyinstaller/xpath_explorer.spec`
- 명령: `pyinstaller packaging/pyinstaller/xpath_explorer.spec`

### 품질 점검 명령
- `python scripts/check_docs_sync.py --strict-warnings`
- `python scripts/run_quality_checks.py --strict-doc-warnings`
- `pytest -q`

### 구현 점검 반영 항목 (요약)
- Playwright launch 실패 시 자원 정리 강화
- BatchScenarioWorker 실패 시그널/재시도 메타데이터 추가
- 시나리오 성공률 기준 토스트/요약 판정 보정
- 설정 저장/복원 4개 키 반영
- 로거 파일 핸들러 폴백 + Markdown 테이블 escape 보강
- 종료 시 워커 정리 helper 일관화
