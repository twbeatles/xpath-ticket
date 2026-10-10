# Project Audit

감사 기준일: 2026-10-10
대상: XPath Explorer v4.4 (`xpath-ticket`, 현재 패키지 `xpath_explorer/`)
방법: `README.md`·`CLAUDE.md`·`docs/claude.md`·`CHANGELOG.md` 정독, CodeGraph MCP 우선 분석 후 grep·직접 열람·테스트 실행으로 보완. 코드는 수정하지 않음(본 보고서 파일만 신규 작성/갱신).
이전 감사: 루트의 기존 `PROJECT_AUDIT.md`(v4.3 기준, 2026-08-21)는 본 감사로 대체한다. v4.3에서 수정 예고된 항목이 실제 반영됐는지도 재확인했다.
후속(2026-10-10): 본 문서의 High-Risk 5건과 주요 갭은 v4.5(`CHANGELOG.md` 참고)에서 반영했다. 아래 본문은 감사 시점 기록으로 유지한다.

---

## 1. Executive Summary

이 프로젝트는 티켓 사이트 자동화를 위한 PyQt6 데스크톱 XPath 탐색·검증 도구다. v4.3 감사에서 지적된 고위험 항목(오버레이 미동작, 이중 엔진 단절, API 키 평문 저장, 쿠키 평문·도메인 미분리, 종료 시 미저장 손실, 미리보기 중첩 실행, CSV 수식 주입, URL 스킴, 시나리오 무제한 대기, 설정 스키마 침묵 실패, QSettings 키)은 **모두 코드상 수정이 확인**됐다 (`CHANGELOG.md` v4.3 절과 일치. 관련 테스트 33개 실행·통과).

전체 위험도는 **Medium**이다. 앱이 뜨지 않거나 데이터를 광범위하게 날리는 치명 결함은 확인되지 않았다. 다만 v4.4 현재 코드에서 **이중 엔진(Selenium/Playwright) 대응의 잔재**가 시나리오 실행기와 Diff 분석에 남아 있고, **실시간 티켓 사이트를 향한 실클릭 버튼에 확인 절차가 없으며**, **구버전이 남긴 평문 API 키 파일을 여전히 읽어 사용**한다. 세 가지는 실제 사용에서 바로 체감될 수 있는 문제다.

가장 중요한 문제 3~5개:

1. [ISSUE-001] Playwright-only 상태에서 시나리오 실행이 빈 결과로 "완료"되고, 팝업/창 액션은 항상 Selenium만 본다 (High, Confirmed).
2. [ISSUE-002] 클릭 테스트가 확인 없이 실제 브라우저 클릭을 수행한다 (Medium, Confirmed).
3. [ISSUE-003] 구버전 `ai_config.json`에 남은 평문 API 키를 환경변수 없이 계속 사용한다 (Medium, Confirmed — 런타임 재현).
4. [ISSUE-004] Diff 분석이 Selenium 전용이며 실행 가드가 없다 (Medium, Confirmed).
5. [ISSUE-005] 쿠키 저장 시 원자적 쓰기의 `.bak` 백업이 평문으로 남고 권한 제한도 없다 (Medium, Confirmed).

데이터 손상/유실 가능성: XPath 목록 자체는 dirty 확인 + 원자적 저장으로 보호된다. 다만 **비정상 종료 시 복구 파일이 없어**(자동저장 없음) 크래시하면 미저장 작업이 날아가고, 쿠키·(레거시)API 키 같은 비밀의 디스크 잔재(`.bak` 포함)는 여전하다. 대규모 사용자 데이터 파괴 경로는 없다.

가장 먼저 수정해야 할 영역: `workers/scenario_worker.py`의 엔진 게이트·윈도우 액션 라우팅(ISSUE-001) → 클릭 테스트 확인 절차(ISSUE-002) → 레거시 키 정리(ISSUE-003) 순이다.

---

## 2. Project Understanding

### 프로젝트 목적

인터파크/멜론티켓/YES24 등 복잡한 티켓팅 사이트에서 XPath를 추출·검증·관리하고 Selenium/Playwright/PyAutoGUI 코드를 생성하는 PyQt6 데스크톱 앱이다. `CLAUDE.md`는 `docs/claude.md`를 정본으로 지정한다. `AGENTS.md`는 저장소에 없다(6장 참고).

### 주요 entrypoint

```text
python -m xpath_explorer
  └─ xpath_explorer/__main__.py
       └─ xpath_explorer/main_window.py (facade)
            └─ xpath_explorer/app/main_window.py::main()
                 ├─ configure_qt_env() → require_qt() → QApplication → XPathExplorer.show() → app.exec()
레거시 래퍼: "xpath 조사기(모든 티켓 사이트).py" → 동일 main()
```

`XPathExplorer`는 `ExplorerToolsMixin + ExplorerDataMixin + ExplorerBrowserMixin + ExplorerUIMixin + QMainWindow` 조합이다. Qt가 없으면 `_HeadlessXPathExplorer`가 `require_qt()`로 즉시 실패한다(의도에 부합).

### 핵심 모듈

| 계층 | 위치 | 역할 |
|---|---|---|
| 조립 | `app/main_window.py` | 매니저/상태 생성, QSettings 이관, UI 초기화 순서 고정 |
| Selenium | `browser/browser.py` facade + `selenium_*.py` | 창/프레임/피커/검증. `RLock` 직렬화, 검증 세션 힌트 캐시 |
| Playwright | `browser/playwright.py` facade + `playwright_parts/` | 스캔·DOM·수명주기 분리. `pw_manager` |
| 엔진 선택 | `browser/engine_router.py` | `source_engine` 기준 Selenium/Playwright 라우팅 |
| 워커 | `workers/*_worker.py` + `driver_guard.py` | QThread. 진입 가드·미리보기 동기 정지 |
| 저장 | `core/paths.py::atomic_write_json` | 설정·통계·AI 설정·쿠키의 원자적 저장(+`.bak`) |
| 스키마 | `core/config.py::SiteConfig.from_dict` | 항목 검증· coerce·`items` 비리스트 거부 |
| 안전장치 | `tools/csv_safety.py`, `core/url_safety.py`, `core/cookie_safety.py` | CSV 수식 무력화·URL 스킴 허용목록·쿠키 도메인 분리 |
| AI | `ai/assistant.py` + `ai/config.py` | 키는 메모리에만, 디스크에는 provider/model만 |

### 데이터 저장 방식

DB를 쓰지 않는다. 사용자 XPath 목록은 사용자가 고른 경로의 JSON(원자적 저장), 앱 상태는 `~/.xpath_explorer/`(`ai_config.json`·`statistics.json` 등, 쓰기 불가 시 temp 폴백·최후 메모리 전용), 창 설정은 `QSettings("XPathExplorer", ...)`(구 `MyCompany` 키 1회 이관)이다.

### 외부 의존성

필수: PyQt6, selenium, undetected-chromedriver, webdriver-manager. 선택: playwright(Chromium 설치는 고정 argv `subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"])`, 셸 미사용 — 주입 경로 없음), openai, google-genai(둘 다 optional import, 부재 시 명확한 에러·규칙 기반 폴백).

### 핵심 실행 흐름

```text
검증(단건): 편집기 입력 → _test_xpath → engine_router(source_engine) → Selenium/Playwright validate → 결과창·하이라이트·통계
전체 검증(F5): _validate_all → ValidateWorker(browser, playwright) → 항목별 엔진 라우팅 → _record_validation_outcome(태그/창/프레임·성공률 기록)
배치: runner(가드+미리보기 정지) → BatchTestWorker(항목별 라우팅) → CSV/Markdown 리포트(수식 무력화)
시나리오: dialog(둘 중 하나라도 alive면 시작) → BatchScenarioWorker → validate 계열은 항목별 라우팅, wait/popup/창 전환은 Selenium 고정(ISSUE-001)
피커: chk_overlay → start_picker(overlay_mode) → picker_overlay_bootstrap + PICKER_SCRIPT 주입 → PickerWatcher
쿠키: 저장 전 경고 → atomic_write_json + chmod 600 시도 / 불러오기: JSON 리스트 검증 → 도메인 분리 → 성공/실패 집계 → refresh
AI: 다이얼로그 입력 → configure(키 메모리 보관) → persistable 저장(키 제외) → 로드 시 파일+환경변수 병합(ISSUE-003)
종료: _confirm_discard_unsaved → 워커 정지·Playwright 종료·통계 shutdown·Selenium 종료 → accept
```

---

## 3. Audit Coverage & Limitations

### 실제 확인한 주요 모듈

`app/main_window.py`, `browser/engine_router.py`, `browser/selenium_validation_parts/visual.py`(클릭), `browser/selenium_windows.py`, `browser/dom_export.py`, `browser/selenium_dom.py`, `mixins/browser/{validation,preview,picker,navigation,export,context}.py`, `mixins/data/{files,cookies}.py`, `mixins/tools/batch/{runner,scenario,reports}.py`, `mixins/tools/inspection/dom_diff.py`, `mixins/tools/inspection/diff_panel.py`, `workers/{scenario,batch,validate,preview,ai,diff}_worker.py`, `workers/driver_guard.py`, `workers/worker_shared.py`, `ai/{assistant,config,providers}.py`, `tools/csv_safety.py`, `core/{url_safety,cookie_safety,config,config_state,paths}.py`, `analysis/statistics.py`, `state/history.py`, `browser/playwright_parts/lifecycle/install.py`.

### CodeGraph로 분석한 호출 관계

CodeGraph MCP(`codegraph_explore`) 6회 호출로 entrypoint·피커/검증·엔진 라우터·AI/쿠키/종료·클릭/안전장치·시나리오/가드·DOM 번들·설정/통계·미리보기/AI 워커의 호출·역호출(blast radius)·동적 디스패치 경계를 확인했다. 주요 흐름: `_click_test_xpath → _active_validation_browser → resolve_browser_for_item`, `closeEvent → statistics.save → atomic_write_json`, `BatchScenarioWorker ← runner/scenario + tests`, `exclusive_driver_worker_running ← lifecycle/preview` 등이다.

### 실행한 테스트

의존성 없이 실행 가능한 범위에서 직접 실행했다(PyQt6·Selenium이 없는 환경이라 Qt/Selenium 의존 테스트는 수집 자체가 불가 — 아래 한계 참고):

- `test_csv_safety.py`, `test_url_safety.py`, `test_cookie_safety.py`, `test_ai_config_precedence.py`, `test_engine_router.py`, `test_picker_overlay_script.py`, `test_js_asset_syntax.py`, `test_config_schema.py`, `test_atomic_json_write.py` — **33 passed**.
- `scripts/check_docs_sync.py` — Errors 0, Warnings 0.
- `scripts/check_encoding_health.py` — 244 files, decode 실패 0, mojibake 0.
- 레거시 키 재현 프로브(`/tmp` 격리 스크립트, `Path.home` 일시 교체): 파일에만 키가 있고 환경변수가 없을 때 `load_ai_config`가 파일 키를 그대로 반환함을 확인 — `legacy openai key loaded without env: True`.
- 전체 수집 시도: 140개 수집 + 15개 모듈 수집 에러(모두 `PyQt6`/`selenium` 부재 causes). 실패가 아니라 **환경 미충족**이다.

### 확인하지 못한 환경/외부 서비스

실제 Chrome/Selenium 세션, Playwright Chromium, 티켓 사이트 실페이지, OpenAI/Gemini 실 API, PyInstaller 빌드 산출물, Windows 레지스트리 QSettings 실동작, macOS/Linux 경로 동작. Qt 필요 테스트(`pytest.mark.qt`)와 브라우저 의존 테스트는 미실행이다.

### CodeGraph·분석상의 한계

- 인덱스가 `archive/` 레거시 단일 파일의 동명 심볼(`XPathExplorer`, `BrowserManager` 등)을 현재 패키지와 묶어 blast radius가 부풀려 보인다. 본 감사는 `xpath_explorer/` 기준으로 재확인했다.
- `getattr` 기반 동적 디스패치(`switch_to_frame`, `wait_for_popup`, `begin_validation_session` 등)는 정적 추적만으로 실제 분기를 단정할 수 없어, 해당 경로는 소스 직접 열람으로 보완했다.
- 런타임 재현은 비밀·브라우저가 필요 없는 1건(ISSUE-003)만 수행했고, 나머지는 코드 흐름 확정 + 테스트 명세 대조로 판단했다. 신뢰도 표기는 이 기준을 따른다.

---

## 4. High-Risk Issues

### [ISSUE-001] Playwright-only 시나리오가 빈 결과로 "완료"되고 창 액션은 Selenium 고정

* **위치:** `xpath_explorer/workers/scenario_worker.py::run` (게이트), `_run_window_action` (윈도우 액션), `xpath_explorer/mixins/tools/batch/scenario.py::start_run` (다이얼로그 게이트)
* **우선순위:** High
* **신뢰도:** Confirmed
* **문제:** 워커 진입 게이트가 Selenium(`self.browser.is_alive()`)만 검사한다. 다이얼로그는 Selenium·Playwright 둘 중 하나라도 살아 있으면 시작을 허용하므로, Playwright만 켠 사용자가 시나리오를 실행하면 워커가 결과를 0건으로 `completed`를 쏘고 끝난다. 또한 `wait_for_popup`·`switch_latest_popup`·`switch_window_by_title`·`switch_root_window`는 `self.browser`(Selenium) 고정이라 Playwright 팝업을 절대 못 보고 "popup not found"로 실패한다. `validate_item`·`validate_xpath` 계열만 항목별 엔진 라우팅을 탄다.
* **발생 조건:** (a) Selenium을 닫고 Playwright만 실행한 채 시나리오 실행. (b) Playwright 세션의 팝업을 기다리거나 창을 전환하는 스텝 포함(양쪽 다 켜져 있어도 실패).
* **영향:** "시나리오 완료" 표시와 함께 0건 요약이 나와 성공처럼 보인다. 팝업 대기 스텝은 Playwright 세션에 팝업이 있어도 실패한다. Playwright 중심 사용자에게 시나리오 실행기가 사실상 고장 난 것처럼 동작한다.
* **근거:**
  - `scenario_worker.py:264`: `if not self.browser.is_alive(): self.completed.emit(results, False, scenario_name); return` — Playwright 검사가 없다.
  - `scenario_worker.py:216-255`: `_run_window_action` 전체가 `self.browser`의 `wait_for_popup`·`switch_to_*`만 사용한다.
  - `mixins/tools/batch/scenario.py:241-244`: 다이얼로그는 `not self.browser.is_alive() and not pw_alive`일 때만 막는다 — 워커 게이트와 정합이 어긋난다.
* **반증 확인:** 항목별 라우팅(`_engine_browser_for_item`, batch/validate/scenario의 validate 계열)은 확인했고, 다이얼로그의 `pw_alive` 검사도 확인했다. 그러나 진입 게이트와 윈도우 액션 경로는 라우팅을 타지 않음을 소스에서 직접 확인했으므로 반증되지 않는다. `BatchTestWorker`·`ValidateWorker`는 항목별 라우팅을 하므로 F5/배치는 해당 없음 — 시나리오 워커만의 문제다.
* **호출/영향 범위:** CodeGraph 기준 `BatchScenarioWorker` 호출자 25곳(다이얼로그·리포트·runner·facade). 영향은 시나리오 실행 경로 한정. Selenium 전용 사용자는 영향 없음.
* **권장 수정 방향:** 워커 진입 게이트를 "Selenium 또는 Playwright 중 유효 엔진이 하나라도 있고, 스텝이 요구하는 엔진이 살아 있음"으로 변경하고, 빈 결과 완료 시 "실행된 스텝 0건 — 요구 엔진 미연결"을 명시한다. `_run_window_action`을 엔진별로 분기한다(Playwright 측 popup 대기·창 전환 API가 있으면 사용, 없으면 해당 스텝을 `window_action_not_supported_for_engine`으로 명확히 실패). 다이얼로그 시작 전에 스텝별 요구 엔진과 연결 상태를 미리 검증하는 것이 가장 좋다.
* **필요한 회귀 테스트:** (Unit) `run()` 게이트: Selenium dead + Playwright alive + playwright 스텝 → 빈 완료가 아니라 스텝 실행. Fake 양쪽 매니저로 검증. (Unit) `wait_for_popup` 스텝이 Playwright 세션의 팝업을 보는지, Selenium 고정이면 실패 메시지가 엔진을 명시하는지. (Integration) 다이얼로그 `start_run` 게이트와 워커 게이트의 허용 조건 일치 테스트.

### [ISSUE-002] 클릭 테스트가 확인 절차 없이 실제 클릭을 수행

* **위치:** `xpath_explorer/mixins/browser/validation.py::_click_test_xpath`
* **우선순위:** Medium
* **신뢰도:** Confirmed
* **문제:** v4.4 신규 "클릭 테스트" 버튼이 토스트 한 줄(`"요소 클릭 시도 중..."`)만 띄우고 곧바로 `click_element`를 호출한다. Selenium 경로는 스크롤→일반 클릭→ActionChains 폴백, Playwright 경로는 `scroll_into_view_if_needed + click`으로 실제 페이지에 작용한다. 티켓팅 사이트에서 이 클릭은 예매 이동·팝업 오픈·수량 변경 등 되돌리기 어려운 부작용을 낼 수 있다. 클릭 후 창/프레임 목록을 새로고침하지 않아, 페이지가 이동했으면 이후 검증이 stale 컨텍스트에서 돈다.
* **발생 조건:** 사용자가 검증indi 목적으로 클릭 테스트를 누르고, 해당 XPath가 상태 변경 요소(예매·결제·삭제 버튼)인 경우. 오버레이 모드(클릭 차단)와 정반대 작용이라, 오버레이로 안전에 익숙해진 사용자가 더 쉽게 누른다.
* **영향:** 의도하지 않은 예매 흐름 진입·폼 제출. 최악의 경우 결제 단계까지 진행될 수 있는 사이트 특성상 "검증용 클릭"의 기대와 다르다.
* **근거:** `_click_test_xpath(:140-181)`에 확인 다이얼로그·경고 문구가 없고, 성공 시 `🖱️ 클릭 성공`만 표시한다. 클릭 후 `_refresh_windows`·`_scan_frames` 호출이 없다.
* **반증 확인:** 피커의 오버레이(클릭 방지)와는 별개 경로임을 확인했다. 프레임 복구(`finally`의 `switch_back`)는 있으나 페이지 내비게이션 자체를 막지 못한다. "사용자가 버튼을 직접 눌렀다"는 점은 고의 조작을 막지 못한다는 반증이 되지 않는다(기대 위반이 핵심).
* **호출/영향 범위:** 편집기 클릭 버튼 1곳 → 양 엔진의 `click_element`. 영향은 클릭된 실페이지 한정.
* **권장 수정 방향:** 클릭 전 확인 다이얼로그("실제 페이지에 클릭합니다. 예매·결제로 이어질 수 있습니다")를 기본 켜짐으로 두고, 성공 후 창/프레임 목록을 갱신한다. 부작용이 큰 사이트용으로 "스크롤만 하기(클릭 없음)" 옵션을 함께 두면 검증 목적에 충분하다.
* **필요한 회귀 테스트:** (Unit, Qt) 버튼 핸들러가 확인 다이얼로그에서 `No`를 고르면 `click_element`가 호출되지 않는지(Fake 엔진 호출 횟수 0). (Unit) `Yes` 후 창/프레임 갱신 함수가 호출되는지. (E2E, 수동) 실페이지 이동 후 후속 검증이 정상 동작하는지.

### [ISSUE-003] 구버전이 남긴 평문 API 키 파일을 계속 읽어 사용

* **위치:** `xpath_explorer/ai/config.py::load_ai_config`, `xpath_explorer/ai/assistant.py::_save_config`
* **우선순위:** Medium
* **신뢰도:** Confirmed
* **문제:** v4.3부터 신규 저장은 키를 제외(`persistable_ai_config`)하고 환경변수가 파일보다 우선한다. 그러나 v4.2 이하에서 이미 기록된 `~/.xpath_explorer/ai_config.json` 안의 `openai_api_key`·`gemini_api_key`는 로드 시 그대로 병합되고, 해당 provider의 환경변수가 없을 때 유효한 키로 쓰인다. `_save_config`는 재설정할 때만 파일을 덮어쓰므로, 한 번도 재설정하지 않은 사용자의 디스크 평문 키는 영구히 살아 있고 계속 사용된다.
* **발생 조건:** v4.2 이하에서 다이얼로그로 키를 저장한 적이 있고, v4.3+로 업데이트 후 환경변수를 설정하지 않았거나(또는 한 provider만 설정) 재설정을 하지 않은 경우.
* **영향:** "파일에 키를 저장하지 않는다"는 v4.3 릴리즈 노트·README 설명과 달리, 과거 키가 공유 PC·백업·동기화 폴더에 남아 사용된다. 키 유출 시 과금·남용 위험.
* **근거:** `config.py:24-39` — 파일 전체를 `config.update(file_config)`로 병합한 뒤 환경변수 키만 덮어쓴다. 파일 유래 키를 버리는 로직이 없다. 런타임 재현(환경변수 제거 + 파일에 레거시 키만 존재): `openai_api_key`가 그대로 로드됨을 실행으로 확인했다.
* **반증 확인:** 신규 저장 경로(`persistable_ai_config`)와 환경변수 우선은 테스트(`test_ai_config_precedence.py`, 7개 통과)로 확인했다. 그러나 이는 *신규* 동작만 보장하고, 레거시 파일의 키를 무효화하지 않으므로 반증되지 않는다. 마이그레이션 정리 코드·관련 테스트는 없다.
* **호출/영향 범위:** `load_ai_config` 호출자는 assistant 초기화 경로 2곳. 영향은 레거시 키 보유 사용자 + 해당 키로 호출되는 OpenAI/Gemini API.
* **권장 수정 방향:** 로드 시 파일 유래 `*_api_key`를 무시(또는 읽되 즉시 파일에서 삭제 후 로그)하는 1회 마이그레이션을 둔다. 예: 파일에 비밀 키가 있으면 키를 제거한 파일을 원자적으로 다시 쓰고 `logger.warning("레거시 평문 키 N건을 제거했습니다. 환경변수를 설정하세요")`. README에 "업데이트 후 첫 실행 시 기존 파일의 키는 자동 파기" 한 줄을 추가한다.
* **필요한 회귀 테스트:** (Unit) 파일에 레거시 키 + 환경변수 없음 → 반환 config에 키 없음 + 파일에서 키 제거됨. (Unit) 환경변수 있음 → 환경변수 키 사용 + 파일 키는 제거됨. 기존 `test_ai_config_precedence.py`에 레거시 케이스 2개를 추가한다.

### [ISSUE-004] Diff 분석이 Selenium 전용·무가드로 실행

* **위치:** `xpath_explorer/mixins/tools/inspection/diff_panel.py::run_analysis`
* **우선순위:** Medium
* **신뢰도:** Confirmed
* **문제:** `DiffAnalyzeWorker(list(self.config.items), self.browser, self.diff_analyzer)`에 항상 Selenium 브라우저를 넘긴다. 실행 전 alive 검사도, `_abort_if_driver_busy` 가드도 없다. Playwright만 켠 상태에서는 전 항목이 "찾지못함"으로 나온다. 검증/배치/시나리오 실행 중에 Diff 분석을 열면 같은 WebDriver를 두 워커가 공유한다(종료 시에는 정리되나 실행 중 경합은 막지 못한다).
* **발생 조건:** (a) Playwright 세션으로 작업하면서 Diff 분석 실행. (b) F5/배치/시나리오 실행 중 Diff 분석 실행.
* **영향:** (a) 실제 변경이 없어도 "찾지못함 N개"로 보여 오판 유발. (b) 프레임/창 컨텍스트 경합으로 양쪽 결과가 흔들릴 수 있다(Selenium `RLock`은 호출 단위 직렬화라 세션 단위 경합은 남는다).
* **근거:** `diff_panel.py:158-167` — 가드·게이트 없이 워커 생성·시작. 대조적으로 `validation.py:189-196`, `runner.py:84-86`, `scenario.py:260-262`는 alive 검사 + `_abort_if_driver_busy` + `_stop_live_preview_sync`를 모두 수행한다.
* **반증 확인:** DOM Diff *리포트*(`dom_diff.py`)는 Selenium→Playwright 폴백과 기준선 소스 추적을 갖추고 있어 정상이다. 그러나 항목 *분석*(`diff_panel.py` + `diff_worker.py::get_element_info`) 경로는 Selenium 고정임을 확인했으므로 반증되지 않는다. AI 워커는 브라우저를触지 않아 제외가 정당하나, Diff 워커는 `self.browser.get_element_info`를 호출하므로 가드 대상이다.
* **호출/영향 범위:** Diff 분석 다이얼로그 1곳. 영향은 분석 결과 신뢰도 + 동시 실행 시 드라이버 경합.
* **권장 수정 방향:** 다른 실행 경로와 동일하게 alive 검사 + `_abort_if_driver_busy("Diff 분석")`를 둔다. `DiffAnalyzeWorker`에 `playwright`를 전달하고 항목별 라우팅을 적용하거나, 최소한 Playwright-only 상태에서는 "Selenium 연결 필요"를 명시한다.
* **필요한 회귀 테스트:** (Unit) 실행 중(validate/batch/scenario Fake 가동) Diff 시작 → 거부 토스트. (Unit) Selenium dead + Playwright alive → 명확한 안내(또는 Playwright 경로 분석). (Unit) 다이얼로그 종료 시 cancel+wait 정리.

### [ISSUE-005] 쿠키 `.bak` 백업이 평문·무권한으로 잔류

* **위치:** `xpath_explorer/core/paths.py::atomic_write_json`, `xpath_explorer/mixins/data/cookies.py::_save_cookies`
* **우선순위:** Medium
* **신뢰도:** Confirmed
* **문제:** `atomic_write_json`은 교체 전 기존 파일을 `.bak`으로 복사한다. 쿠키 저장(`_save_cookies`)은 대상 파일에만 `chmod 0o600`을 시도하고, `.bak`(이전 쿠키 전문)에는 권한을 걸지 않으며 삭제하지도 않는다. Windows에서는 `chmod`가 사실상 무효라 경고 다이얼로그("암호화 없이 저장")가 유일한 보호가 된다. 즉 로그인 세션이 평문 2벌(본체+백업)로 남는다.
* **발생 조건:** 같은 경로에 쿠키를 2회 이상 저장한 경우 항상. 대상 파일이 없어 첫 저장만 한 경우는 `.bak`이 없다.
* **영향:** 세션 탈취에 쓸 수 있는 쿠키가 사용자 의식 밖에 하나 더 남는다. 백업·동기화·공유 PC에서 노출면이 2배다. 일반 설정 JSON의 `.bak`은 무해에 가깝지만 쿠키는 민감하다.
* **근거:** `paths.py:56,64-71` — 백업 복사 후 권한·정리 없음. `cookies.py:56-60` — `chmod`는 저장 본체에만, 실패 무시. Windows `chmod` 한계는 표준 동작이다.
* **반증 확인:** 저장 전 경고·도메인 분리·원자적 쓰기(v4.3 수정)는 확인했다. 그러나 `.bak` 잔류와 Windows 권한 한계는 코드상 그대로이므로 반증되지 않는다. 통계·AI 설정의 `.bak`은 민감도가 낮아 쿠키가 핵심이다.
* **호출/영향 범위:** `atomic_write_json` 호출자 11곳 중 민감 파일을 쓰는 곳은 쿠키 저장. 영향은 쿠키 저장 사용자의 디스크.
* **권장 수정 방향:** `atomic_write_json`에 `backup: bool = True` 옵션을 두고 쿠키 저장에서는 `backup=False`로 호출하거나, 백업에도 동일 `chmod`를 적용 후 다음 저장 성공 시 이전 `.bak`을 삭제한다. 저장 다이얼로그 경고에 ".bak 백업도 함께 남을 수 있음"(또는 남지 않음 — 선택한 구현대로) 한 줄을 반영한다.
* **필요한 회귀 테스트:** (Unit) 쿠키 2회 저장 시나리오에서 `.bak` 정책(없음 또는 0o600)이 지켜지는지(POSIX). (Unit) Windows 스킵 조건에서 경고 문구가 백업을 언급하는지(문서 동기화 테스트 확장).

---

## 5. Potential Functional Gaps

추정은 추정으로만 표기한다. 버그처럼 단정하지 않는다.

1. **쿠키 도구가 Selenium 전용 (Likely Gap).** `_save_cookies`·`_load_cookies`는 `self.browser.driver`(Selenium)만 쓴다. `PlaywrightStorageMixin`에 저장/로드 API는 있으나 UI 연결을 찾지 못했다. Playwright 세션으로 로그인한 사용자는 쿠키를 저장·복원할 수 없다. README의 "쿠키 관리" 설명은 엔진을 구분하지 않는다.
2. **시나리오에 클릭/입력 액션이 없음 (Confirmed Gap).** 지원 액션은 `validate_item`·`validate_xpath`·`wait/sleep`·`wait_for_popup`·창 전환 3종뿐이다(`scenario_worker.py:311-383`, 기본 예제 `scenario.py:80-82`). v4.4에 클릭 테스트 버튼이 생겼지만 시나리오에서 클릭 스텝은 여전히 불가다. README 표현("팝업/대기 액션") 자체는 정확하나, 매크로 수준 재현을 기대하면 빈 기능이다.
3. **시나리오 `retries` 상한 없음 (Confirmed Gap, Low).** `wait_seconds`는 60초 상한이 있으나 `retries`는 무제한이다. 취소는 attempt마다 체크되어 무한 점유는 아니다(`_run_validate_with_retry:180-193` 확인). 과대한 값은 실행 시간만 늘린다. 상한(예: 10) + 로드 시 경고를 권장한다.
4. **비정상 종료 복구 없음 (Confirmed Gap).** 정상 종료의 미저장 확인은 있으나 자동저장·크래시 복구 스냅샷이 없다. `atomic_write_json`·`resolve_storage_dir` 인프라가 있는데 목록 자동저장에는 미사용이다.
5. **내보내기(CSV/HTM/코드)가 비원자적 쓰기 (Confirmed Gap, Low).** 설정 저장과 달리 `open(..., "w")` 직접 쓰기라 크래시 시 반쪽 파일이 남는다. 재내보내기로 복구 가능해 심각도는 낮다.
6. **AI 네트워크 호출에 명시적 timeout 없음 (추정).** `assistant.py`의 OpenAI·Gemini 호출에 timeout 인자가 없다. AI 워커 스레드라 UI는 안 막히고, 종료 시 `wait(WORKER_WAIT_TIMEOUT)` 후 진행하므로 먹통 가능성은 낮다. 사용 중인 SDK의 기본 timeout을 확인하지 못했으므로 추정으로만 둔다. 명시적 timeout(예: 30초) + 실패 시 폴백 유지를 권장한다.
7. **`atomic_write_json` tmp 이름이 pidのみ (추정, Low).** 같은 프로세스·같은 파일에 대한 동시 호출이 같은 tmp 경로를 쓴다. 현재 호출자는 UI 스레드·통계 라이터가 이벤트로 직렬화되어 실제 경합은 확인되지 않았다. 스레드 식별자 포함을 고려할 수 있다.
8. **설정 기본 파일명에 `config.name` 원문 사용 (추정, Low).** `files.py:95`의 `f"{self.config.name}.json"` — `from_dict`가 name의 경로 문자를 소독하지 않는다. 다이얼로그에서 사용자가 고치면 되나, `/`·`..` 포함 이름은 기본 경로가 엉뚱해진다.
9. **AI 메모리 내 키가 provider 전환 후에도 남음 (Likely Gap, Low).** `configure()`는 현재 provider 키만 갱신하고 이전 provider 키를 메모리 config에서 지우지 않는다. 디스크에는 기록되지 않으므로 노출은 없으나, 세션 중 provider를 바꾸면 이전 키가 메모리에 잔류한다.
10. **DOM 번들 내 원본 HTML을 직접 열면 페이지 스크립트가 동작 (Likely Gap, Low).** 리포트 HTM은 전역 이스케이프(`_safe`, `dom_export.py:137` 등)라 안전함을 확인했다. 그러나 번들 속 `documents/*.html`은 재분석용 원본이라 브라우저로 열면 스크립트가 실행될 수 있다. 사용자 본인이 캡처한 페이지라 위험은 낮지만, 번들에 "원본 HTML 직접 열기 주의" 한 줄을 권장한다.

---

## 6. Documentation Mismatches

README·CLAUDE·코드를 대조했다. v4.3 감사 때의 불일치(오버레이·무제한 Undo·키 저장·엔진 단절)는 모두 해소된 것을 확인했다.

1. **`AGENTS.md` 없음.** 작업 지시 기준으로 확인할 문서 목록에 있으나 저장소에 없다. `CLAUDE.md`→`docs/claude.md` 체계가 대신하므로 실무 문제는 없다. 없음을 명시한다.
2. **"Playwright 세션으로 검증" 표현의 적용 범위.** README의 "Playwright에서 가져온 항목은 Playwright 세션이 살아 있을 때 그 엔진으로 검증/하이라이트합니다"는 단건·전체·배치·미리보기에서 구현을 확인했다. 그러나 시나리오의 창/팝업 액션(ISSUE-001)과 Diff 항목 분석(ISSUE-004)은 Selenium 전용이라, "시나리오 자동화"·"검증" 일반 표현까지 같은 보장을 읽으면 어긋난다. 해당 2개 경로의 엔진 제약을 문서에 한 줄씩 추가해야 한다.
3. **"API 키 미저장"과 레거시 파일.** README·CHANGELOG 표현은 신규 저장 기준으로는 정확하다. 다만 ISSUE-003처럼 구버전 파일의 키는 계속 사용되므로, "v4.3 이전에 저장된 키는 첫 실행 시 자동 파기(예정)" 같은 이행 문구가 필요하다(현재 없음).
4. **품질 게이트의 실행 전제.** README의 `pytest -q`는 PyQt6·Selenium이 없는 환경에서 15개 모듈 수집 에러를 낸다(본 감사 환경에서 확인). 게이트 자체는 틀리지 않았으나 "전체 의존성 설치 후" 전제가 설치 절과 멀리 떨어져 있다. 의존성 미설치 시 `pytest -q`가 아닌 순수 로직 subset 명령을 문서에 덧붙이면 재현성이 좋아진다.
5. 그 외 모델명(`gpt-5.4`·`gemini-flash-latest`), Undo 50단계 상한, 쿠키 경고·도메인 분리, 시나리오 60초 상한, QSettings 이관, 원자적 저장 적용 범위는 문서와 일치한다.

---

## 7. Recommended Fix Plan

실제 코드는 수정하지 않는다. 아래는 순서 제안이다.

### Phase 1 — Immediate

데이터·주요 기능·보안 직결. ISSUE-001/002/003이다.

1. 시나리오 엔진 게이트·윈도우 액션 라우팅(ISSUE-001). 다이얼로그와 워커의 허용 조건을 일치시키고, Playwright 창/팝업 액션을 지원하거나 명확히 실패시킨다.
2. 클릭 테스트 확인 절차(ISSUE-002). 확인 다이얼로그 기본 켜짐 + 클릭 후 창/프레임 갱신.
3. 레거시 평문 키 정리(ISSUE-003). 로드 시 파일 유래 키 무시 + 1회 자동 파기 + 로그·문서 반영.

### Phase 2 — Stability

예외 처리, 입력 검증, 상태 관리, OS 호환성. ISSUE-004/005 + 확정 갭이다.

1. Diff 분석에 alive 검사·드라이버 바쁨 가드·엔진 라우팅(ISSUE-004).
2. 쿠키 `.bak` 정책(백업 제외 또는 권한·정리) + Windows 한계 문서화(ISSUE-005).
3. 쿠키 도구의 Playwright 세션 지원(Likely Gap 1).
4. 시나리오 `retries` 상한 + 과대값 경고(Gap 3).
5. 비정상 종료 대비 자동저장 스냅샷(Gap 4, `atomic_write_json` 재사용).
6. 내보내기 경로 원자적 쓰기 확대(Gap 5).

### Phase 3 — Structural

1. AI 호출 명시적 timeout·재시도 정책(Gap 6).
2. 설정명 파일명 소독 + provider 전환 시 메모리 키 정리(Gap 8·9).
3. Qt 의존 코드를 UI 뒤로 격리해 headless 테스트 가능 영역 확대(현재 Qt 테스트는 환경 의존).
4. `archive/`를 인덱스·검색 기본 범위에서 제외해 CodeGraph 오염 방지(감사 한계에서 확인된 문제).

---

## 8. Test Recommendations

"테스트 추가"가 아니라 입력 조건과 기대 결과를 명시한다. Qt/Selenium 의존은 `pytest.mark.qt` 분리 유지, 실사이트·실쿠키·실키는 쓰지 않는다.

### Unit

| 대상 | 입력 조건 | 기대 결과 |
|---|---|---|
| 시나리오 게이트 | Selenium dead + Playwright alive, playwright 스텝 1개 | 스텝이 실행되고 `completed(results≠[], ...)` |
| 시나리오 창 액션 | Playwright 팝업 존재 + `wait_for_popup` 스텝 | 팝업 검출 성공(또는 엔진 미지원 명시 실패) |
| 클릭 확인 | 다이얼로그 `No` 선택 | Fake `click_element` 호출 0회 |
| 클릭 후 갱신 | 다이얼로그 `Yes` + 가짜 내비게이션 | `_refresh_windows`·`_scan_frames` 호출 |
| 레거시 키 | 파일에만 구키 + env 없음 → `load_ai_config` | 반환에 키 없음 + 파일에서 키 제거 |
| 레거시 키(env) | 파일 구키 + env 신키 | env 키 사용 + 파일 키 제거 |
| Diff 가드 | validate/batch/scenario Fake 가동 중 분석 시작 | 거부 토스트, 워커 미시작 |
| Diff 엔진 | Selenium dead + Playwright alive | 안내 메시지(또는 PW 경로 결과) |
| 쿠키 백업 | 동일 경로 2회 저장(POSIX) | `.bak` 없음 또는 0o600 |
| retries 상한 | `retries: 10^9` 시나리오 로드 | 상한 클램프 + 경고(또는 명시 실패) |
| URL | `file:///C:/a.html`·`about:blank`·`javascript:alert(1)` | 허용·허용·거부 메시지 |

### Integration

- F5 전체 검증: Selenium/Playwright 혼합 목록에서 항목별 엔진으로 검증되고, PW 세션 종료 항목은 `browser_not_connected`로 명확히 실패한다.
- 배치 리포트: `=cmd`·`+sum`·`@link` 선행 셀이 `'` 접두로 무력화되어 저장된다(기존 `test_batch_report_exports.py` 확장).
- 종료 흐름: dirty 상태에서 `Save` 선택 후 다이얼로그 취소 → 종료 중단(`a0.ignore`); 저장 성공 → 종료 진행.
- 시나리오 다이얼로그를 닫으면 워커가 cancel+wait로 정리된다(`on_dialog_close` 경로 테스트 없음 — 신규).

### End-to-End (수동, 실브라우저)

- Playwright만 켠 상태: 스캔 → 편집기 적용 → Ctrl+T 검증 → F5 → 시나리오(팝업 포함) → Diff 분석까지 끊김 없이 수행된다.
- 클릭 테스트 후 페이지가 이동해도 후속 검증·창 목록이 정상이다.

### Concurrency

- 미리보기 입력 중 F5: 이전 미리보기 워커가 `wait`로 정리된 뒤 검증이 시작된다(현재 `wait` 추가됨 — 경합 재발 방지 회귀).
- 배치 실행 중 Diff 분석·피커 시작이 거부된다.
- AI 생성 중 앱 종료: `WORKER_WAIT_TIMEOUT` 내 정리되고 스레드 누수 없이 종료된다.

### Regression

- v4.3 수정 11종(오버레이·미저장 확인·엔진별 검증·키 미저장·쿠키 경고/도메인·미리보기 wait·CSV·URL·시나리오 60초·스키마 거부·QSettings 이관)에 대한 기존 테스트를 유지하고, 본 감사의 ISSUE-001~005 테스트를 같은 파일군에 추가한다.

### Platform-specific

- Windows 잠금 파일에 `atomic_write_json` 실패 시 원본 보존(기존 테스트는 덤프 실패 케이스만 — OS 잠금 케이스 추가).
- `chmod 0o600` 무효 환경(Windows)에서 쿠키 경고 문구가 백업 잔류를 고지하는지.
- 한글 포함 경로(레거시 래퍼 파일명 등)에서 설정 저장·내보내기가 정상 동작하는지.

---

## 9. Final Assessment

| 영역 | 평가 | 근거 |
|---|---|---|
| Functional Correctness | Needs Work | 단건·전체·배치 검증과 스캔·피커·쿠키·AI 기본 흐름은 견고하나, 시나리오(ISSUE-001)와 Diff 분석(ISSUE-004)에 엔진 라우팅 잔재가 있다 |
| Runtime Stability | Acceptable | 워커 가드·미리보기 wait·세션 복구·종료 정리가 갖춰져 있다. AI timeout 명시 같은 잔여가 있다 |
| Data Integrity | Acceptable | dirty 확인·원자적 저장·스키마 검증이 있다. 크래시 복구 부재와 쿠키 `.bak` 잔류가 감점이다 |
| Error Resilience | Acceptable | 폴백(AI)·실패 집계(쿠키)·세션 힌트 무효화가 있다. 시나리오 빈 완료 표시처럼 실패를 성공처럼 보이는 1건이 있다 |
| Cross-platform Robustness | Acceptable | URL 스킴·인코딩 검사가 깨끗하다. `chmod` Windows 한계와 Qt/Selenium 미설치 시 테스트 불가 구조가 감점이다 |
| Test Confidence | Needs Work | 순수 로직 140개 수집·33개 실행 통과·문서/인코딩 게이트 통과이나, Qt·브라우저 의존 핵심 경로(검증·배치·시나리오 워커)는 본 환경에서 미실행이다 |

**실제로 먼저 수정할 문제 3개:**

1. **[ISSUE-001] 시나리오 Playwright 게이트·창 액션 라우팅 (High)** — 주요 기능이 조건부로 동작하지 않는 유일한 High다.
2. **[ISSUE-003] 레거시 평문 API 키 자동 파기 (Medium)** — 런타임 확정 + 수정이 작고(로드 1곳) 보안 효과가 크다.
3. **[ISSUE-002] 클릭 테스트 확인 절차 (Medium)** — 티켓 도메인 특성상 한 번의 사고 비용이 크고 수정이 다이얼로그 1개 수준이다.
