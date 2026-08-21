# Project Audit

감사 기준일: 2026-08-21  
대상: XPath Explorer v4.3 (`xpath-ticket`)  
후속: 본 감사의 1·2단계 수정과 문서/릴리즈 반영은 v4.3에서 완료. Selenium 소스 재포맷은 별도 작업으로 남김.  
방법: `README.md` 정독, `CLAUDE.md` 부재 확인, CodeGraph MCP로 엔트리포인트/호출 관계/영향 범위 분석, 필요한 경우에만 현재 패키지 소스와 테스트를 보조 확인.  
범위: 기능 구현상 실제 문제가 될 수 있는 부분. 코드 수정은 하지 않음.

---

## 1. Executive Summary

이 프로젝트는 레거시 단일 파일 GUI를 계층형 패키지로 분리한 PyQt6 데스크톱 앱이다. 설정 스키마 강제 변환, 원자적 JSON 저장, 워커 취소, 창/프레임 복구, 검증 세션 캐시 등 **안정성 장치는 이미 꽤 들어가 있다.** 단위 테스트도 워커/설정/경로/DOM 리포트 중심으로 넓게 깔려 있다.

다만 사용자에게 보이는 핵심 기능 몇 개가 문서와 다르거나, 엔진이 둘로 갈라져 있으며, 세션 비밀이 평문으로 남는다. 전체 위험도는 **Medium-High**다. 앱이 즉시 못 뜨는 수준의 치명 결함은 확인되지 않았지만, 티켓팅 자동화 도구로서 **세션 쿠키/API 키 유출**, **오버레이 모드 무력화**, **Selenium/Playwright 이중 엔진 불일치**, **종료 시 작업 손실**은 실제 사용에서 바로 체감될 가능성이 높다.

핵심 문제 요약:

| 영역 | 핵심 소견 | 우선순위 |
|------|-----------|----------|
| Visual Picker | `overlay_mode`가 UI에서 넘어가지만 `start_picker()`가 사용하지 않음. 클릭은 JS에서 항상 가로챔 | High |
| 이중 엔진 | Playwright 스캔 결과는 `source_engine=playwright`로 저장되나, 검증/라이브 미리보기/배치는 Selenium `BrowserManager`만 사용 | High |
| 보안 | `ai_config.json`에 API 키 평문 저장, 쿠키 JSON도 평문. 파일 권한이 제한되지 않음 | High |
| 상태 | `closeEvent`가 미저장 XPath 목록을 묻지 않고 종료 | High |
| 비동기 | 라이브 미리보기 워커가 이전 스레드를 기다리지 않고 새로 시작. Picker/Validate와 같은 WebDriver를 공유 | High |
| 문서 | `CLAUDE.md` 없음. README의 “무제한 Undo/Redo”, 오버레이 모드, 환경변수 우선순위가 구현과 불일치 | Medium |
| 테스트 | facade/워커/스키마는 있으나, 오버레이, 쿠키 mixin, 메인 윈도우 통합, 이중 엔진 경로는 거의 없음 | Medium |

CodeGraph blast radius 기준으로 `XPathExplorer`, `start_picker`, `ExplorerDataCookiesMixin`, `load_ai_config`는 호출은 많지만 해당 심볼 자체의 직접 테스트가 없거나 매우 얇다.

---

## 2. Project Understanding

### 2.1 목적

README 기준, 인터파크/멜론티켓/YES24 같은 복잡한 티켓팅 사이트에서 XPath를 추출·검증·관리하고, Selenium/Playwright/PyAutoGUI 코드를 생성하는 PyQt6 데스크톱 도구다.

`CLAUDE.md`는 저장소에 없다. 개발 규칙은 `README.md`의 품질 게이트 절, `docs/PROJECT_STRUCTURE_ANALYSIS.md`, `scripts/check_docs_sync.py` / `run_quality_checks.py`에 흩어져 있다.

### 2.2 실행 흐름

```text
python -m xpath_explorer
        └─ xpath_explorer/__main__.py
              └─ xpath_explorer.main_window.main
                    └─ xpath_explorer/app/main_window.py::main()
                          ├─ configure_qt_env()
                          ├─ require_qt()
                          ├─ QApplication
                          └─ XPathExplorer.show() / app.exec()

레거시 래퍼: "xpath 조사기(모든 티켓 사이트).py" → 동일 main()
```

`XPathExplorer`는 mixin 조합으로 조립된다.

```text
ExplorerToolsMixin
ExplorerDataMixin
ExplorerBrowserMixin
ExplorerUIMixin
QMainWindow
```

초기화 순서 (`app/main_window.py::__init__`):

1. `BrowserManager`, `SiteConfig.from_preset("인터파크")`, 통계/코드생성/옵티마이저/히스토리/AI/Diff 생성
2. 워커 핸들과 미리보기/검색 디바운스 타이머 준비
3. `init_settings()` → `QSettings("MyCompany", "XPathExplorer")`
4. `_init_ui()` → `_load_settings()` → `_setup_timers()` → `_refresh_table()` → `_reset_history_baseline()`

종료 흐름 (`mixins/tools/lifecycle_tools.py::closeEvent`):

1. 타이머 정지, geometry/`_save_settings()` 저장
2. Picker/Validate/LivePreview/AI/Diff/Batch/Scenario/Install 워커 취소 후 `wait(WORKER_WAIT_TIMEOUT)`
3. Playwright 매니저 close, 통계 shutdown, Selenium `browser.close()`
4. 이벤트 `accept()` — 미저장 확인 없음

### 2.3 주요 모듈과 호출 관계

CodeGraph 기준으로 실제 런타임 경로는 아래와 같다. `archive/251221 xpath 조사기(모든 티켓 사이트).py`에도 동명 심볼이 남아 인덱스가 자주 레거시를 끌어오므로, 본 감사는 현재 패키지 `xpath_explorer/`를 기준으로 한다.

| 계층 | 위치 | 역할 |
|------|------|------|
| Facade | `xpath_explorer/main_window.py`, `workers/background.py`, `mixins/*_mixin.py` | 하위 호환 re-export |
| UI 조립 | `mixins/ui/` | 메뉴, 패널, 단축키 |
| 브라우저 UI | `mixins/browser/` | 네비게이션, 피커, 미리보기, 검증, DOM 내보내기 |
| 데이터 | `mixins/data/` | 설정 파일, 쿠키, 편집기, 필터, QSettings |
| 도구 | `mixins/tools/` | 배치/시나리오, Playwright 스캔, AI, 진단 |
| Selenium | `browser/selenium_*.py` + `selenium_validation_parts/` | 창/프레임/피커/검증. `RLock`으로 드라이버 직렬화 |
| Playwright | `browser/playwright.py` + `playwright_parts/` | 별도 프로세스/브라우저. `pw_manager` |
| 워커 | `workers/*_worker.py` | QThread. 대부분 `BrowserManager`를 공유 |
| 저장 | `core/paths.py::atomic_write_json` | 설정/통계/AI 설정 |
| 스키마 | `core/config.py::SiteConfig.from_dict` | 항목 검증, 중복 이름 거부, 타입 coerce |

### 2.4 README와 구현이 맞는 부분

- 패키지 엔트리 `python -m xpath_explorer`와 레거시 래퍼가 모두 `app/main_window.py::main()`으로 모인다.
- 내보내기 메뉴는 JSON/CSV/Python Selenium/JavaScript 네 가지다 (`mixins/ui/menu.py`).
- 배치 테스트, 시나리오 실행기, 매크로, 템플릿, DOM Diff, 쿠키, 스크린샷, 검증 히스토리, 텔레메트리, 진단 메뉴가 실제로 존재한다.
- `atomic_write_json`은 설정 저장과 AI 설정 저장에 사용된다.
- AI 기본 모델명은 README와 코드가 같다: `gpt-5.4`, `gemini-flash-latest`.

---

## 3. High-Risk Issues

### 3.1 오버레이 모드가 UI만 있고 동작하지 않음

* 위치: `xpath_explorer/mixins/browser/picker.py::_start_picker` → `xpath_explorer/browser/selenium_picker.py::BrowserPickerMixin.start_picker` → `xpath_explorer/core/browser_assets/picker.py::PICKER_SCRIPT`
* 문제: 체크박스 `chk_overlay` 값이 `start_picker(overlay_mode=...)`로 전달되지만, `start_picker` 본문이 `overlay_mode`를 전혀 쓰지 않는다. Picker JS는 클릭마다 항상 `preventDefault()`/`stopPropagation()`을 호출한다.
* 영향: README와 툴팁(“체크 시 버튼이 클릭되지 않고 선택만”)과 반대로, 체크 여부와 무관하게 페이지 클릭이 항상 가로채진다. 사용자는 오버레이를 끈 뒤 실제 클릭 동작을 확인하려고 해도 불가능하다. 레거시 archive 구현은 overlay 여부에 따라 안내 문구를 바꿨다.
* 근거:

```70:70:xpath_explorer/mixins/browser/picker.py
        self.browser.start_picker(overlay_mode=self.chk_overlay.isChecked())
```

```82:101:xpath_explorer/browser/selenium_picker.py
    def start_picker (self ,overlay_mode :bool =False ):
        """요소 선택 모드를 시작하고 모든 윈도우/iframe에 picker를 주입합니다."""
        with self ._lock :
            ...
                    self .driver .execute_script (PICKER_SCRIPT )
```

```239:248:xpath_explorer/core/browser_assets/picker.py
    function onClick(e) {
        ...
        e.preventDefault();
        e.stopPropagation();
```

CodeGraph: `start_picker` 호출자는 `mixins/browser/picker.py`, `workers/picker_worker.py` 두 곳. 해당 심볼 직접 테스트 없음.
* 권장 수정 방향: JS 주입 시 `overlay_mode`를 인자/전역 플래그로 넘기고, 비오버레이일 때만 기본 클릭을 통과시키거나, 체크박스를 제거하고 “클릭은 항상 선택 전용”으로 문서를 맞출 것.
* 우선순위: High

### 3.2 Playwright로 수집한 항목을 Selenium으로만 검증한다

* 위치: `xpath_explorer/mixins/tools/playwright_tools.py` (스캔/하이라이트, `_editing_source_engine = "playwright"`) vs `mixins/browser/validation.py::_test_xpath`, `mixins/browser/preview.py::_update_live_preview`, `workers/validate_worker.py`, `workers/batch_worker.py`
* 문제: Playwright 스캔에서 편집기로 가져온 항목은 `source_engine="playwright"`로 저장된다. 그러나 Ctrl+T 검증, F5 전체 검증, 배치, 라이브 매칭 카운트는 전부 `self.browser`(Selenium `BrowserManager`)만 본다. 미리보기는 Playwright 항목이면 Selenium 창 핸들을 비우고 URL/title만 넘긴다.
* 영향: Playwright 브라우저와 Selenium 브라우저가 다른 세션/팝업/iframe에 있으면, 방금 스캔한 XPath가 “없음”으로 나온다. README의 “Playwright 자동 스캔 → 사용 클릭 → 편집기/목록” 흐름이 검증 단계와 단절된다.
* 근거: CodeGraph상 `pw_manager.scan_elements` / `highlight`는 Playwright 쪽, `ValidateWorker`/`BatchTestWorker`/`LivePreviewWorker`는 `self.browser.validate_xpath` / `count_elements`만 호출. `_test_xpath`는 `self.browser.is_alive()`가 거짓이면 바로 실패한다.
* 권장 수정 방향: `source_engine == "playwright"`이고 `pw_manager`가 살아 있으면 검증/하이라이트/카운트를 Playwright 경로로 보내거나, 스캔 결과를 Selenium 세션으로 재적용하는 브리지를 만들 것. 최소한 UI에 “이 항목은 Playwright 세션 전용” 경고를 띄울 것.
* 우선순위: High

### 3.3 AI API 키가 홈 디렉터리 JSON에 평문으로 저장된다

* 위치: `xpath_explorer/ai/assistant.py::configure` / `_save_config`, `xpath_explorer/ai/config.py::load_ai_config`, 저장 경로 `~/.xpath_explorer/ai_config.json`
* 문제: `configure()`가 `openai_api_key` / `gemini_api_key`를 JSON에 그대로 쓴다. 파일 권한 제한, DPAPI/keyring, 마스킹이 없다. 로드 시 **파일 내용이 환경변수를 덮어쓴다.**
* 영향: 공유 PC, 백업, 동기화 폴더에 키가 남는다. README는 환경변수(`OPENAI_API_KEY`, `GEMINI_API_KEY`)를 설정 수단으로 안내하지만, 한 번 다이얼로그에서 저장하면 env가 무시된다. 테스트도 이 우선순위를 고정하고 있다 (`tests/test_ai_config_precedence.py`: `file_key`가 `env_key`를 이김).
* 근거:

```14:34:xpath_explorer/ai/config.py
def load_ai_config(logger: Logger) -> Dict[str, Any]:
    ...
    if openai_key:
        config["openai_api_key"] = openai_key
    ...
            if isinstance(file_config, dict):
                config.update(file_config)  # 파일이 env를 덮어씀
```

```115:146:xpath_explorer/ai/assistant.py
        self._config[f"{provider}_api_key"] = api_key
        return self._save_config()
        ...
            compat.atomic_write_json(config_path, self._config)
```

* 권장 수정 방향: 키는 OS 자격 증명 저장소 또는 권한 0600 파일 + 환경변수 우선. 파일에는 provider/model만 저장. README의 우선순위를 코드와 테스트에 맞출 것.
* 우선순위: High

### 3.4 로그인 세션 쿠키가 평문 JSON으로 저장된다

* 위치: `xpath_explorer/mixins/data/cookies.py::ExplorerDataCookiesMixin`
* 문제: `driver.get_cookies()` 결과를 사용자 선택 경로에 `json.dump`로 저장한다. 원자적 쓰기 없음, 암호화 없음, 도메인 제한 없음. 로드 시 현재 페이지 도메인과 맞지 않는 쿠키도 `add_cookie`를 시도하고, 실패만 집계한다. 성공 후 `driver.refresh()`로 세션을 바로 적용한다.
* 영향: 티켓 사이트 로그인/예매 세션이 디스크에 남는다. 잘못된 도메인에서 로드하면 일부만 적용되어 “로그인이 된 것 같은데 좌석은 안 됨” 같은 부분 실패가 난다. CodeGraph: 이 mixin은 `data_mixin`에서만 쓰이고 **직접 테스트가 없다.**
* 근거:

```33:89:xpath_explorer/mixins/data/cookies.py
    def _save_cookies(self):
        ...
                cookies = driver.get_cookies()
                with open(fname, 'w', encoding='utf-8') as f:
                    json.dump(cookies, f)
    def _load_cookies(self):
        ...
                for cookie in cookies:
                    try:
                        driver.add_cookie(cookie)
```

레거시 archive는 `sameSite`/`storeId`/`id`를 제거하고 도메인별 기본 경로를 썼다. 현재 코드는 그 호환 처리가 없다.
* 권장 수정 방향: 민감 쿠키 저장 경고, 현재 URL 도메인과 일치하는 항목만 주입, `sameSite` 호환 처리, `atomic_write_json`, 가능하면 암호화. 저장 기본 경로를 `resolve_storage_dir()/cookies`로 고정하고 권한을 제한할 것.
* 우선순위: High

### 3.5 종료 시 미저장 XPath 목록을 버리지 않고 닫는다

* 위치: `xpath_explorer/mixins/tools/lifecycle_tools.py::closeEvent`
* 문제: 종료 시 UI geometry/폰트/프리셋만 저장한다. `self.config.items`는 사용자가 `_save_config()`로 파일을 고르지 않으면 디스크에 남지 않는다. `closeEvent`는 확인 없이 `a0.accept()`한다.
* 영향: 피커로 수십 개 수집한 뒤 창을 닫으면 작업이 사라진다. README의 “안전한 상태 관리 / 작업 손실 완벽 방지”와 어긋난다. Undo는 메모리 `HistoryManager`뿐이고 프로세스 종료와 함께 소멸한다.
* 근거: `closeEvent` 본문은 워커 정지 + `_save_settings()` + 브라우저 종료만 수행. `_save_config()` 호출 없음. `_new_config`/`_on_preset_changed`만 확인 대화상자가 있다.
* 권장 수정 방향: dirty 플래그(마지막 저장 스냅샷과 `config.to_dict()` 비교)를 두고, 종료/새 설정/프리셋 전환 시 저장 여부를 물을 것. 자동 복구용 세션 스냅샷을 `atomic_write_json`으로 쓰는 것도 검토.
* 우선순위: High

### 3.6 라이브 미리보기 워커가 이전 작업을 기다리지 않고 중첩 실행된다

* 위치: `xpath_explorer/mixins/browser/preview.py::_update_live_preview`, `xpath_explorer/workers/preview_worker.py::LivePreviewWorker`
* 문제: XPath 입력마다 디바운스 후 새 `LivePreviewWorker`를 시작한다. 이전 워커가 돌고 있으면 `cancel()`만 호출하고 `wait()`하지 않는다. cancel은 `Event` 플래그라 `count_elements()` 도중에는 중단되지 않는다. 같은 `BrowserManager`를 PickerWatcher, ValidateWorker, BatchWorker도 공유한다.
* 영향: 입력 중 매칭 카운트가 깜빡이거나, 피커 주입/창 전환과 프레임이 엇갈릴 수 있다. Selenium `RLock`이 호출 단위로는 직렬화하지만, `validate_xpath`가 락을 여러 번 잡았다 놓으면 그 사이에 미리보기가 창/프레임을 바꿀 수 있다. UI는 `request_id`로 stale 결과를 버리므로 표시는 비교적 안전하나, **브라우저 컨텍스트 자체는 안전하지 않다.**
* 근거:

```74:132:xpath_explorer/mixins/browser/preview.py
            if self.live_preview_worker and self.live_preview_worker.isRunning():
                self.live_preview_worker.cancel()
            ...
            self.live_preview_worker = worker
            worker.start()
```

`LivePreviewWorker.run()`은 시작 시 창/프레임을 바꾸고 `finally`에서 복구한다. 테스트(`tests/test_live_preview_worker.py`)는 FakeBrowser에서 `run()`을 동기 호출할 뿐, 중첩 start/cancel을 검증하지 않는다.
* 권장 수정 방향: 새 워커 시작 전 `wait()`하거나, 단일 워커 + 최신 xpath만 실행하는 큐로 바꿀 것. 피커 활성 중에는 라이브 미리보기를 멈출 것. 드라이버 락을 검증 세션 전체로 확장할 것.
* 우선순위: High

### 3.7 Picker 툴팁이 페이지 텍스트를 `innerHTML`에 삽입한다

* 위치: `xpath_explorer/core/browser_assets/picker.py` (`onMouseOver`, `lock`)
* 문제: `xpath`, `css`, `tag`, `text`를 템플릿 리터럴로 `tooltip.innerHTML`에 넣는다. HTML 이스케이프가 없다. 대상 페이지가 이미 실행 중인 브라우저라 심각도는 웹앱 XSS보다 낮지만, 피커 UI를 통해 주입 스크립트가 돌 수 있다.
* 영향: 악성/변조된 DOM 속성·텍스트가 피커 오버레이에서 실행되면 `__pickerResult`를 조작하거나 키 입력을 가로챌 수 있다. 티켓 사이트 자체보다는, 열린 창에 악성 iframe이 있을 때 의미가 있다.
* 근거:

```229:235:xpath_explorer/core/browser_assets/picker.py
        tooltip.innerHTML = `
            <div><strong>태그:</strong> ${tag}</div>
            <div><strong>XPath:</strong> ${xpath}</div>
            ...
            ${text ? `<div><strong>텍스트:</strong> ${text}</div>` : ''}
```

XPath 리터럴 생성(`xpathLiteral`)은 잘 되어 있으나, HTML 삽입 경로와는 별개다.
* 권장 수정 방향: `textContent` 기반 DOM 생성 또는 HTML escape. 잠금 UI 버튼은 `createElement`로 붙일 것.
* 우선순위: Medium

### 3.8 CSV 내보내기에 수식 주입 방어가 없다

* 위치: `xpath_explorer/mixins/data/files.py::_export` (`fmt == 'csv'`), `xpath_explorer/mixins/tools/batch/reports.py::_batch_results_to_csv`
* 문제: 이름/XPath/설명/메시지를 `csv.writer` / `csv.DictWriter`에 그대로 넣는다. 셀이 `=`, `+`, `-`, `@`로 시작하면 스프레드시트가 수식으로 해석할 수 있다. Markdown 쪽은 `_escape_markdown_cell`이 있으나 CSV는 대응이 없다.
* 영향: 페이지에서 가져온 텍스트/XPath를 CSV로 열어 분석할 때 로컬 Excel/LibreOffice 수식 실행 위험이 있다. 배치 리포트의 `msg`/`xpath` 컬럼이 특히 노출면이 넓다.
* 근거: `_export` CSV 분기와 `_batch_results_to_csv`에 prefix escape가 없음. 패키지 안에 `csv_safety` 모듈은 현재 존재하지 않는다(디렉터리 스냅샷의 pyc만 남아 있을 수 있음).
* 권장 수정 방향: CSV 셀 선행 `=+-@` / 탭을 따옴표 이스케이프 또는 `'=` prefix로 무력화하는 공통 helper를 쓰고, 파일 내보내기와 배치 리포트 양쪽에 적용할 것.
* 우선순위: Medium

### 3.9 URL 이동이 `http(s)`만 허용하도록 강제되어 `file://` / `about:` 가 깨진다

* 위치: `xpath_explorer/mixins/browser/navigation.py::_navigate`
* 문제: `http://`/`https://`가 아니면 무조건 `https://`를 붙인다. `file:///C:/page.html` → `https://file:///C:/page.html`. `about:blank`도 동일. 브라우저 열기(`_toggle_browser`)는 `about:blank`를 허용한다.
* 영향: 로컬 HTML 픽스처나 저장된 DOM 스냅샷을 다시 열어 검증하는 흐름이 실패한다. `javascript:` 같은 위험 스킴은 우연히 차단되지만, 의도와 예외 처리가 아니라 부작용이다.
* 근거:

```139:145:xpath_explorer/mixins/browser/navigation.py
        url = self.input_url.text().strip()
        if not url: return
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            self.input_url.setText(url)
```

* 권장 수정 방향: 허용 스킴 화이트리스트(`http`, `https`, `about`, 옵션으로 `file`). `javascript:`, `data:`는 거부. 호스트만 입력된 경우에만 `https://`를 붙일 것.
* 우선순위: Medium

### 3.10 시나리오 `wait` 시간에 상한이 없다

* 위치: `xpath_explorer/workers/scenario_worker.py::_normalize_steps`, `run`의 `wait`/`sleep` 분기, `_run_window_action(wait_for_popup)`
* 문제: `seconds`를 `float`로만 받고 `max(0.0, ...)`만 한다. 상한 없음. JSON을 불러오면 파싱만 하고 액션/타임아웃을 미리 검증하지 않는다. 알 수 없는 액션은 실행 중 `unsupported_action`으로 실패 처리된다(크래시는 아님).
* 영향: `{"action":"wait","seconds":86400}`이면 워커가 하루 동안 점유한다. 종료 시 `wait(WORKER_WAIT_TIMEOUT)` 후 disconnect하지만, 스레드가 `Event.wait` 루프에 있으면 타임아웃까지 UI가 멈춘 것처럼 보일 수 있다. `wait_for_popup`도 동일하게 긴 timeout을 바이트 그대로 사용한다.
* 근거: `_to_float` + `max(0.0, wait_seconds)`. `start_run()` 검증은 `dict` + `steps` 리스트 여부만 본다 (`mixins/tools/batch/scenario.py`).
* 권장 수정 방향: step당 wait/popup timeout 상한(예: 60s), 시나리오 로드 시 액션 화이트리스트 사전 검증, 취소가 타임아웃 루프를 실제로 끊는지 테스트할 것.
* 우선순위: Medium

### 3.11 Selenium 드라이버 소스의 토큰 간격/한글 주석 손상

* 위치: `xpath_explorer/browser/selenium_driver.py`, `selenium_picker.py`, `selenium_windows.py`, `selenium_validation_parts/lookup.py`
* 문제: `def start_picker (self ,overlay_mode :bool =False ):`, `self ._lock =RLock ()`처럼 식별자 사이 공백이 들어가 있고, 주석이 `WebDriver 묎렐 곷젹`처럼 모지바케다. Python 문법상 동작은 하지만, 인코딩/자동 포맷 사고가 코드 전역에 남아 있다.
* 영향: 이후 패치/리뷰/검색이 어렵고, 비슷한 변환이 문자열 리터럴까지 건드리면 런타임 버그가 된다. README가 강조하는 `check_encoding_health.py`의 대상이 바로 이 계층이다.
* 근거: CodeGraph가 해당 파일들을 그대로 반환. `create_driver`, `start_picker`, `count_elements` 본문이 모두 이 스타일이다.
* 권장 수정 방향: 해당 파일을 정상 포맷(black/ruff)으로 재기록하고, 품질 게이트에서 토큰 사이 이상 공백/모지바케를 fail 처리할 것. 기능 변경 없이 재포맷 PR을 따로 둘 것.
* 우선순위: Medium

### 3.12 QSettings 조직명이 플레이스홀더다

* 위치: `xpath_explorer/app/main_window.py::init_settings` — `QSettings("MyCompany", "XPathExplorer")`
* 문제: Windows 레지스트리/ini 경로가 `MyCompany` 아래로  mo인다. 레거시는 `QSettings("XPathExplorer", "v3")`였다.
* 영향: 구버전에서 쓰던 창 위치/폰트/마지막 프리셋이 마이그레이션되지 않는다. 기능 버그는 아니지만, “설정이 초기화됐다”로 보인다.
* 근거: `init_settings` 한 줄. archive와 키가 다름.
* 권장 수정 방향: org/app 이름을 제품명으로 고정하고, 구 키가 있으면 한 번 읽어 이관할 것.
* 우선순위: Low

### 3.13 Undo/Redo는 무제한이 아니다

* 위치: `xpath_explorer/core/runtime_constants.py::HISTORY_MAX_SIZE = 50`, `xpath_explorer/state/history.py::HistoryManager.push_state`
* 문제: README는 “무제한 Undo/Redo”를 약속한다. 구현은 50개에서 앞쪽 스냅샷을 버린다.
* 영향: 대량 편집 후 초반 작업을 되돌릴 수 없다. 히스토리 자체는 RLock + deepcopy로 비교적 견고하고 테스트(`tests/test_history_manager.py`)가 있다.
* 근거: `if len(self._undo_stack) > self._max_history: self._undo_stack.pop(0)`
* 권장 수정 방향: README를 “최대 50단계”로 고치거나, 제한을 UI에 표시할 것.
* 우선순위: Low (문서) / 기능적으로는 의도된 제한일 수 있음

### 3.14 Playwright `highlight`가 `duration_ms`를 JS 문자열에 삽입한다

* 위치: `xpath_explorer/browser/playwright_parts/dom/actions.py::highlight`
* 문제: `el.evaluate(f"""... setTimeout(..., {duration_ms}); ...""")`. 기본값은 int 2000이라 현재 호출(`highlight(element.xpath, 2000)`)은 안전하다. 타입이 보장되지 않으면 JS 삽입이 된다.
* 영향: 현재 공개 UI 경로의 인자는 상수라 **실제 익스플로잇 면은 좁다.** 내부 API가 외부 입력에 열리면 위험해진다.
* 근거: f-string evaluate. `xpath` 자체는 Playwright `xpath=` 셀렉터로 넘어가 별도 문제(잘못된 XPath로 예외)다.
* 권장 수정 방향: `int(duration_ms)`로 클램프하고, evaluate 인자로 넘길 것. XPath는 `xpath=` 접두 전 검증.
* 우선순위: Low

---

## 4. Potential Functional Gaps

아래는 코드로 뒷받침되지만, 제품 의도가 불명확하면 **추정**으로 표시한다.

1. **미저장 확인 부재 (확정)**  
   종료뿐 아니라 `_open_config`도 현재 목록을 바로 교체한다. `_new_config`만 확인한다.

2. **이중 엔진 세션 동기화 없음 (확정 + 추정)**  
   Playwright 스캔 ↔ Selenium 검증 단절은 확정. 쿠키/창 목록을 두 엔진이 공유하지 않는 것은 **추정**으로는 설계 한계일 수 있으나, README는 사용자에게 단일 도구처럼 설명한다.

3. **오버레이 체크박스 의미 소실 (확정)**  
   현재 JS는 항상 클릭을 막으므로, “오버레이 OFF = 실제 클릭” 기능은 빠져 있다.

4. **쿠키 로드 도메인 전제 (확정)**  
   Selenium은 현재 문서 도메인에만 쿠키를 넣는다. 로드 전 해당 URL로 이동하는 단계가 없다. 실패 카운트만 보여 준다.

5. **시나리오에 클릭/입력 액션이 없음 (추정)**  
   지원 액션은 validate/wait/window switch 계열이다. README “팝업/대기 액션이 포함된 시나리오 자동 실행”은 맞지만, 매크로 수준의 click/fill은 시나리오 워커가 아니라 코드 생성 쪽에 있다. 사용자가 시나리오에서 클릭을 기대하면 빈 기능으로 느껴질 수 있다.

6. **`javascript:` URL 명시 차단 없음 (추정)**  
   `_navigate`의 `https://` prefix가 사실상 막는다. 의도가 보안 통제인지는 문서에 없다.

7. **설정 파일 `items`가 리스트가 아니면 빈 목록으로 침묵 로드 (확정)**  
   `SiteConfig.from_dict`는 `raw_items`가 list가 아니면 `[]`로 바꾼다. 잘못된 파일을 “성공”으로 열고 항목이 전부 사라진 것처럼 보인다.

8. **자동 저장/복구 파일 없음 (추정)**  
   `atomic_write_json`과 `resolve_storage_dir()`가 있는데, XPath 목록 오토세이브에는 쓰이지 않는다. 크래시 복구는 없을 가능성이 높다.

9. **워커 중복 실행 가드 불균일 (확정)**  
   피커는 “이미 실행 중”을 막는다. 시나리오 실행기도 running 가드가 있다. F5 검증/배치/라이브 미리보기는 동시에 뜰 수 있다.

10. **Playwright `execute_script`/`inject_script`가 임의 JS를 실행 (추정)**  
    내부 도구 API다. UI에서 사용자 JS 콘솔을 여는지는 이 감사에서 확인하지 못했다. 있으면 그대로 RCE에 가깝다.

11. **Windows에서 `Path.replace` 원자성 (추정)**  
    `atomic_write_json`은 같은 볼륨 replace를 전제한다. 대상 파일이 다른 프로세스로 열려 있으면 Windows에서 실패할 수 있다. 테스트(`tests/test_atomic_json_write.py`)가 있으나 OS 잠금 시나리오는 **추정**으로 약하다.

12. **헤드리스 `XPathExplorer`는 `require_qt()`만 호출 (확정)**  
    Qt 없는 CI에서 클래스 생성 시 즉시 실패하도록 되어 있다. 의도로 보이며, 그 결과 메인 윈도우 통합 테스트가 거의 없다.

13. **문서 공백 (확정)**  
    `CLAUDE.md` 없음. 에이전트/개발 규칙을 README + `docs/PROJECT_STRUCTURE_ANALYSIS.md` + 스크립트에 분산.

14. **레거시 archive가 검색/그래프를 오염 (확정)**  
    동명 `XPathExplorer`/`BrowserManager`가 archive에 남아 CodeGraph가 현재 구현과 레거시를 섞어 반환한다. 유지보수 시 잘못된 파일을 고칠 위험이 있다.

---

## 5. Recommended Fix Plan

### 1단계 — 즉시 수정 (사용자 기능/비밀)

1. **오버레이 모드**  
   JS에 플래그를 연결하거나, 체크박스를 제거하고 문서를 “클릭은 항상 선택 전용”으로 통일.
2. **종료/열기 시 미저장 확인**  
   dirty 감지 + 저장 다이얼로그. 가능하면 `~/.xpath_explorer/autosave.json`에 원자적 스냅샷.
3. **Playwright 항목 검증 경로**  
   `source_engine=playwright`이면 `pw_manager`로 validate/highlight/count. 매니저가 꺼져 있으면 명확한 에러.
4. **비밀 저장**  
   API 키: 파일에 평문 저장 중단, env 우선 또는 OS keyring.  
   쿠키: 저장 경고 + 도메인 필터 + sameSite 호환 + atomic write.
5. **라이브 미리보기 중첩**  
   cancel 후 wait, 또는 단일 워커. 피커 활성 중 미리보기 정지.

### 2단계 — 안정성

1. 시나리오 wait/popup timeout 상한 및 로드 시 액션 화이트리스트.
2. URL 스킴 화이트리스트 (`http(s)`, `about`, 선택적 `file`).
3. CSV 수식 이스케이프를 파일 내보내기/배치 리포트에 적용.
4. Picker `innerHTML` 제거.
5. 워커 동시 실행 정책: Validate/Batch/Preview/Picker 중 하나만 드라이버를 소유.
6. `SiteConfig.from_dict`에서 `items` 타입 오류를 침묵하지 말고 실패시킬 것.
7. QSettings 식별자 정리 및 구버전 키 마이그레이션.

### 3단계 — 구조

1. Selenium `selenium_*.py` 재포맷/재인코딩. archive는 그래프에서 제외하거나 `archive/`를 인덱스 제외.
2. 브라우저 세션 파사드 하나로 Selenium/Playwright를 감싸 창·프레임·검증 API를 통일.
3. Undo 제한을 UI/README에 명시. 세션 복구와 파일 저장을 분리.
4. `CLAUDE.md`(또는 `AGENTS.md`)에 실행 경로, 품질 게이트, “archive는 런타임 아님”을 고정.
5. mixin 거대 파일의 순환 import/`getattr` 디스패치를 줄여 정적 추적 가능하게.

---

## 6. Test Recommendations

기존 테스트는 워커 취소, 설정 스키마, 경로, DOM 리포트, AI 설정 저장, 히스토리 매니저 등 **순수 로직**에 강하다. 아래는 이번 감사에서 구멍이 확인된 부분이다.

### 반드시 추가

| 테스트 | 왜 |
|--------|----|
| `start_picker(overlay_mode=True/False)`가 JS 주입 인자/`window.__pickerOverlay`를 바꾸는지 | 3.1. 현재 시그니처만 있고 동작이 없음 |
| Picker JS: overlay off일 때 `preventDefault` 여부 | 체크박스 계약 |
| Playwright 스캔 항목에 대해 `_test_xpath` / live preview가 `pw_manager`를 쓰는지, Selenium-only일 때 에러 메시지 | 3.2 |
| `_load_cookies`: list가 아닌 JSON 거부(이미 일부 있음), 도메인 불일치 시 실패 집계, `sameSite` 필드가 있어도 크래시 없음 | 3.4, 쿠키 mixin 테스트 전무 |
| `closeEvent` 또는 dirty helper: 변경된 config에서 저장 확인이 필요한지 | 3.5. Qt 테스트로 분리 |
| LivePreview: 이전 워커 `isRunning()` 중 재시작 시 `wait`/`request_id` 및 프레임 복구 순서 | 3.6. 현재 테스트는 동기 `run()`만 |
| `load_ai_config`: 키가 파일에 쓰이지 않거나 env가 이기도록 정책을 바꾸면 기존 `test_ai_config_precedence`도 함께 수정 | 3.3 |

### 보강

| 테스트 | 왜 |
|--------|----|
| `_navigate`: `example.com` → https 부여, `file://`/`about:blank`/`javascript:` 각각 | 3.9 |
| 시나리오 JSON: 미지원 액션, 음수 retries, 과대 `seconds` clamp, 빈 steps | 3.10, `tests/test_batch_scenario_worker.py` 확장 |
| CSV export: `=cmd\|'/c calc'` 형태 셀이 이스케이프되는지 | 3.8, `tests/test_batch_report_exports.py`에 파일 내보내기도 |
| `SiteConfig.from_dict`: `items`가 dict/None일 때 실패 | 3. 잠재 갭 7 |
| `atomic_write_json`: 대상 파일이 읽기 전용/잠금일 때 원본 보존 (Windows) | 3. 잠재 갭 11 |
| Picker tooltip escape: `<img onerror=...>` 텍스트가 innerHTML로 안 들어가는지 | 3.7 |

### 통합/회귀 (가능하면 `pytest.mark.qt`)

- 피커 실행 중 라이브 미리보기/F5가 거부되거나 직렬화되는지.
- 시나리오 실행 중 다이얼로그를 닫으면 `scenario_worker`가 정리되는지 (`on_dialog_close`는 있으나 테스트 없음).
- `XPathExplorer` 생성 후 메뉴 액션 이름/단축키가 README 표와 같은지 (문서 동기화 스크립트 확장).

### 테스트 시 주의

- `archive/`의 동명 클래스를 import하지 말 것. CodeGraph도 이쪽을 자주 가리킨다.
- Qt가 필요한 테스트는 기존처럼 `pytest.mark.qt`로 분리.
- 실 사이트/실 쿠키/실 API 키를 쓰는 테스트는 넣지 말 것.

---

## Appendix: 문서 vs 구현 대조

| README 주장 | 실제 |
|-------------|------|
| 오버레이 모드로 실수 클릭 방지 | 체크박스는 전달만 하고 미사용. 클릭은 JS가 항상 차단 |
| 무제한 Undo/Redo | `HISTORY_MAX_SIZE = 50` |
| 작업 손실 완벽 방지 (`atomic_write_json`) | 파일 저장/AI 설정/통계에만 적용. 목록 오토세이브·종료 확인 없음 |
| AI 키: 다이얼로그 또는 env | 파일 `ai_config.json`이 env를 덮어씀 |
| Playwright 스캔 후 편집기/검증 | 스캔은 Playwright, 검증/미리보기는 Selenium |
| CLAUDE.md 개발 규칙 | 파일 없음 |
| 쿠키로 로그인 상태 유지 | 평문 JSON + 도메인 불일치 시 부분 적용 |

---

## Appendix: CodeGraph 사용 한계

- 인덱스가 `archive/251221 xpath 조사기(모든 티켓 사이트).py`의 거대 클래스를 현재 패키지와 동등한 심볼로 묶어, blast radius/호출자가 부풀었다.
- `selenium_*.py`는 포맷이 깨져 있어 그래프 출력이 읽기 어렵다. 본문은 디스크에서 재확인했다.
- 동적 경계: `getattr(..., "begin_validation_session")`, `getattr(..., "wait_for_popup")` 등. 워커는 구 시그니처 `TypeError` 폴백을 갖고 있어 정적 추적만으로는 실제 분기 누락을 단정하기 어렵다.

감사 범위 밖의 항목(성능 튜닝, UI 스타일, 레거시 파일 삭제 여부)은 기능 리스크로 승격하지 않았다.
