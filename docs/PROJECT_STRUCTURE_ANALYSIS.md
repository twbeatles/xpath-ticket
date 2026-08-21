# XPath Explorer 프로젝트 구조 분석 (2026-08-21)

## 1. 목적
- 현재 코드베이스의 실제 구조, 실행 경로, 품질 게이트, 배포 경로를 한 문서에서 빠르게 파악하기 위한 요약 문서입니다.
- 기준 우선순위는 `코드 > 자동 점검 스크립트 > 문서`입니다.

## 2. 실행/엔트리포인트 구조
- 레거시 실행 래퍼: `xpath 조사기(모든 티켓 사이트).py`
- 패키지 실행 진입점: `xpath_explorer/__main__.py`
- 실제 앱 조립: `xpath_explorer/main_window.py`
- headless/CI Qt 호환 계층: `xpath_explorer/qt_compat.py`
- PyInstaller 스펙: `packaging/pyinstaller/xpath_explorer.spec`

실행 예시:

```bash
python "xpath 조사기(모든 티켓 사이트).py"
python -m xpath_explorer
```

빌드 예시:

```bash
pyinstaller packaging/pyinstaller/xpath_explorer.spec
```

## 3. 패키지 구조

```text
xpath_explorer/
├─ __init__.py
├─ __main__.py
├─ main_window.py
├─ app/
│  └─ main_window.py
├─ qt_compat.py
├─ runtime.py
├─ core/
│  ├─ constants.py
│  ├─ app_constants.py
│  ├─ browser_constants.py
│  ├─ browser_assets/
│  ├─ preset_constants.py
│  ├─ template_constants.py
│  ├─ runtime_constants.py
│  ├─ config_state.py
│  ├─ cookie_safety.py
│  └─ url_safety.py
├─ browser/
│  ├─ browser.py
│  ├─ engine_router.py
│  ├─ playwright.py
│  ├─ selenium_*.py
│  ├─ selenium_validation_parts/
│  ├─ playwright_*.py
│  ├─ playwright_parts/
│  └─ dom_export.py
├─ workers/
│  ├─ background.py
│  ├─ *_worker.py
│  ├─ worker_shared.py
│  └─ driver_guard.py
├─ mixins/
│  ├─ __init__.py
│  ├─ contracts.py
│  ├─ ui_mixin.py
│  ├─ browser_mixin.py
│  ├─ data_mixin.py
│  ├─ tools_mixin.py
│  ├─ ui/
│  ├─ browser/
│  ├─ data/
│  └─ tools/
│     ├─ batch/
│     └─ inspection/
├─ ai/
│  ├─ assistant.py
│  ├─ models.py
│  ├─ config.py
│  ├─ providers.py
│  ├─ prompts.py
│  └─ fallback.py
├─ tools/
│  ├─ ai.py
│  ├─ codegen.py
│  ├─ optimizer.py
│  ├─ xpath_safety.py
│  └─ csv_safety.py
├─ analysis/
│  ├─ diff.py
│  └─ statistics.py
├─ state/
│  └─ history.py
└─ ui/
   ├─ widgets.py
   ├─ components/
   ├─ table_model.py
   ├─ filter_proxy.py
   ├─ styles.py
   └─ theme/
```

## 4. 책임 분리 요약
- `main_window.py`: `xpath_explorer/app/main_window.py`를 재내보내는 호환 facade
- `app/main_window.py`: `XPathExplorer` 조합, 초기 상태/타이머/모듈 초기화
- `qt_compat.py`: PyQt6 import와 headless fallback을 분리해 CI 수집 안정성 보장
- `core/constants.py`: 하위 호환 re-export surface
- `core/*_constants.py`, `xpath_explorer/core/browser_assets/`: 앱/브라우저/UI/프리셋/템플릿/런타임 상수와 JS/selector asset 분리
- `mixins/contracts.py`: split partial mixin이 공유하는 호스트 계약(Protocol)
- `mixins/*_mixin.py`: 하위 호환 facade
- `mixins/ui/`, `mixins/browser/`, `mixins/data/`, `mixins/tools/`: 세부 책임별 partial mixin
- `mixins/*/deps.py`: monkeypatch 안정성을 위한 patch seam
- `browser/engine_router.py`: Playwright/Selenium 항목별 검증 엔진 선택
- `core/url_safety.py`, `core/cookie_safety.py`, `core/config_state.py`: URL 스킴, 쿠키 도메인, 미저장 dirty 판별
- `tools/csv_safety.py`: CSV 수식 주입 무력화
- `workers/driver_guard.py`: 피커/검증/배치/시나리오 드라이버 점유 가드
- `browser/browser.py`: Selenium facade
- `browser/selenium_*.py`, `browser/selenium_validation_parts/`: 창/프레임/검증/피커/DOM 수집 세부 구현
- `browser/playwright.py`: Playwright facade + `NetworkAnalyzer`
- `browser/playwright_*.py`, `browser/playwright_parts/`: lifecycle/network/storage/scan/dom 세부 구현
- `workers/background.py`: 워커 re-export surface
- `workers/*_worker.py`, `worker_shared.py`: Validate/Batch/Scenario/AI/QThread 워커 세부 구현
- `tools/ai.py`: AI public facade, `ai/`: assistant/model/config/provider 내부 구현
- `tools/xpath_safety.py`: XPath literal/attribute/text predicate 생성 공통 helper
- `mixins/tools/inspection_tools.py`: 기능 진단/통계/네트워크/DOM diff facade, `mixins/tools/inspection/`: 세부 UI 구현
- `mixins/tools/batch_tools.py`: 배치 facade, `mixins/tools/batch/`: runner/scenario/report/export 구현
- `ui/widgets.py`, `ui/styles.py`: UI facade, `ui/components/`, `ui/theme/`: 실제 widget/style 구현
- `runtime.py`: 로거, 오류 텔레메트리, 경로 폴백 로깅
- `core/paths.py`: 저장 경로 폴백과 `atomic_write_json()` 기반 JSON 저장 안정성 제공

## 5. 품질 게이트

### 로컬 기본 점검

```bash
python scripts/check_docs_sync.py --strict-warnings
python scripts/check_encoding_health.py
python -m pyright -p .
pytest -q
```

## 6. 스펙 파일 정합성 포인트
- `packaging/pyinstaller/xpath_explorer.spec`는 `ENTRYPOINT_CANDIDATES`로 래퍼/패키지 엔트리포인트를 모두 지원합니다.
- `collect_submodules("xpath_explorer")`를 사용해 분할된 패키지 구조를 빌드 수집합니다.
- `app/`, `ai/`, `ui/components/`, `ui/theme/`, `core/browser_assets/`, `browser/playwright_parts/`, `browser/selenium_validation_parts/`, `mixins/tools/batch/`, `mixins/tools/inspection/`는 spec의 명시 hidden import와 `collect_submodules` 양쪽으로 수집됩니다.
- `xpath_explorer.tools.xpath_safety`, `xpath_explorer.tools.csv_safety`, `xpath_explorer.browser.engine_router`는 동적/간접 import 누락 방지를 위해 hidden import에 명시합니다.
- `qt_excludes`에서 TLS 라이브러리(`libcrypto`, `libssl`)를 제외하지 않는 정책을 유지합니다.
- 선택 의존성(`openai`, `google.genai`, `playwright`)은 설치된 경우에만 hidden import로 포함하며, 릴리즈 스모크에서 import 상태를 점검합니다.
- spec 주석의 품질 점검 명령도 `python -m pyright -p .` 기준으로 유지합니다.

### Qt 테스트 정책
- Qt 런타임이 필요한 테스트는 `pytest.mark.qt`로 분리됩니다.
- 로컬 GUI/Qt 환경에서는 `pytest -q -m qt`로 별도 확인합니다.

## 7. 배포 스펙 정합성
- `packaging/pyinstaller/xpath_explorer.spec`는 다음 엔트리포인트 후보를 사용합니다.
  - `xpath 조사기(모든 티켓 사이트).py`
  - `xpath_explorer/__main__.py`
- `collect_submodules("xpath_explorer")`로 분할 패키지 구조를 자동 수집합니다.
- `xpath_explorer.qt_compat`를 hidden import에 명시해 Qt bootstrap 경로 누락을 방지합니다.
- 기능 진단/배치 export 산출물(`feature_diagnostics_*.md`, `batch_results_*.csv`, `batch_results_*.md`)은 로컬 산출물로 `.gitignore`에서 제외합니다.
- atomic JSON 저장 중 생성될 수 있는 백업/임시 파일(`*.json.bak`, `.*.tmp`)은 로컬 산출물로 `.gitignore`에서 제외합니다.
- `.codegraph/`는 로컬 CodeGraph 인덱스이므로 publish 대상에서 제외합니다.
- `qt_excludes`에는 TLS 관련 라이브러리(`libcrypto`, `libssl`)를 넣지 않습니다.
- 선택 의존성(`openai`, `google.genai`, `playwright`)은 빌드 환경에 설치된 경우에만 hidden import로 추가됩니다.

## 8. 인코딩/Pylance 운영 기준
- `.editorconfig`: `charset = utf-8`, `end_of_line = lf`
- `.vscode/settings.json`
  - `files.encoding = utf8`
  - `files.autoGuessEncoding = false`
  - `python.analysis.diagnosticMode = workspace`
- `pyrightconfig.json`
  - include: `xpath_explorer`, `tests`, `scripts`, `xpath 조사기(모든 티켓 사이트).py`
  - exclude: `archive`, `__pycache__`, `.pytest_cache`, `.pytest_tmp`, `build`, `dist`
- Qt 관련 import는 `TYPE_CHECKING` 분리 또는 `qt_compat.py`를 우선 사용합니다.
- `typeCheckingMode = basic`, `pythonVersion = 3.10`, `reportMissingImports = none`

## 9. 운영 메모
- `archive/`는 보관 영역이며 정적 분석/기본 점검 대상에서 제외됩니다.
- 문서와 코드가 어긋나면 `scripts/check_docs_sync.py`를 우선 기준으로 수정합니다.
- 릴리즈 전에는 `scripts/run_quality_checks.py --strict-doc-warnings --smoke-release` 실행을 권장합니다.
- 배치/시나리오 워커는 기본적으로 원래 창/프레임 문맥을 복구하며, `leave_context: true` 시에만 마지막 문맥을 유지합니다.
- Playwright scan은 현재 프레임, 현재 창 전체 프레임, 모든 팝업/프레임 범위를 지원하고 scan 결과의 창/프레임 출처를 저장합니다.
- 2026-05-03 이후 `XPathItem.source_engine`으로 Playwright 스캔 출처를 저장하고, Playwright page 문맥은 세션 내 안정적인 `pw-page-N` 형식을 사용합니다.
- 임시 구현 리스크 점검 문서는 삭제하고 README/docs 운영 문서에 최종 반영 내용만 유지합니다.
