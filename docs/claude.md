# Claude 운영 가이드 (XPath Explorer)

## 1. 프로젝트 개요
XPath Explorer는 Selenium/Playwright 기반으로 XPath를 수집·검증·분석하는 데스크톱 도구입니다.
호환 실행 진입점은 `xpath_explorer/main_window.py`이고 실제 앱 조립은 `xpath_explorer/app/main_window.py`에서 수행합니다.

## 2. 현재 코드 구조
- 패키지 진입점: `xpath_explorer/__main__.py`
- UI 조립 facade: `xpath_explorer/main_window.py`
- UI 조립 구현: `xpath_explorer/app/main_window.py`
- Qt 호환 계층: `xpath_explorer/qt_compat.py`
- mixin facade: `xpath_explorer/mixins/ui_mixin.py`, `browser_mixin.py`, `data_mixin.py`, `tools_mixin.py`
- split mixin internals: `xpath_explorer/mixins/ui/`, `browser/`, `data/`, `tools/`, `tools/batch/`, `tools/inspection/`
- split mixin contracts/seams: `xpath_explorer/mixins/contracts.py`, `xpath_explorer/mixins/*/deps.py`
- Selenium facade: `xpath_explorer/browser/browser.py`
- Selenium internals: `xpath_explorer/browser/selenium_*.py`, `xpath_explorer/browser/selenium_validation_parts/`
- Playwright facade: `xpath_explorer/browser/playwright.py`
- Playwright internals: `xpath_explorer/browser/playwright_*.py`, `xpath_explorer/browser/playwright_parts/`
- DOM 리포트 렌더러: `xpath_explorer/browser/dom_export.py`
- 워커 facade: `xpath_explorer/workers/background.py`
- 워커 internals: `xpath_explorer/workers/*_worker.py`, `worker_shared.py`
- 상수 facade: `xpath_explorer/core/constants.py`
- 상수 internals: `xpath_explorer/core/*_constants.py`, `xpath_explorer/core/browser_assets/`
- AI facade: `xpath_explorer/tools/ai.py`
- AI internals: `xpath_explorer/ai/`
- UI facade: `xpath_explorer/ui/widgets.py`, `xpath_explorer/ui/styles.py`
- UI internals: `xpath_explorer/ui/components/`, `xpath_explorer/ui/theme/`
- 통계/분석: `xpath_explorer/analysis/statistics.py`, `xpath_explorer/analysis/diff.py`
- 런타임 로깅/텔레메트리: `xpath_explorer/runtime.py`

## 3. 핵심 실행 흐름
1. `app/main_window.py`에서 Qt 환경 변수 설정 후 `QApplication` 생성
2. `XPathExplorer` 초기화 시 Browser/History/Stats/AI 모듈 결합
3. 사용자 액션에 따라 워커 facade(`background.py`) 아래의 개별 워커가 비동기 검증 수행
4. 검증 결과를 통계/히스토리/테이블 모델에 반영
5. 필요 시 DOM export/diff 리포트 생성

하위 호환 원칙:
- 공개 import 경로는 facade에 남기고, 세부 구현 이동은 내부 모듈에서만 수행합니다.
- 테스트 monkeypatch가 facade 심볼을 직접 건드리는 경우를 고려해 `deps.py` seam을 유지합니다.

## 4. 검증 세션/프레임 전략
- `xpath_explorer/browser/browser.py`의 `begin_validation_session()`은 프레임 목록/힌트/미스 캐시를 세션 단위로 유지합니다.
- 미스 캐시는 TTL 기반(`VALIDATION_MISS_TTL_SECONDS`)이며 프레임 시그니처가 바뀌면 무효화합니다.
- 배치 검증 워커는 동일 세션을 재사용해 중복 스캔을 줄입니다.

## 4-1. 팝업/창 문맥 전략
- 항목 스키마는 `found_window`, `found_window_title`, `found_window_url`, `found_frame`를 함께 보존합니다.
- 단건 검증/하이라이트/스크린샷은 다음 우선순위를 사용합니다.
  1. 사용자가 창 콤보를 명시적으로 변경한 경우 해당 창
  2. 현재 선택 항목의 저장된 창 문맥
- Selenium 창 매핑 순서는 `handle -> exact URL -> exact title`입니다.
- 대상 창을 찾지 못하면 다른 창으로 자동 폴백하지 않고 실패시킵니다.
- 수동 프레임 스캔은 `get_all_frames(force_refresh=True)`로 캐시를 강제 갱신합니다.
- 시나리오 워커는 `wait_for_popup`, `switch_latest_popup`, `switch_window_by_title`, `switch_root_window` 액션을 지원합니다.
- 배치/시나리오 워커는 기본적으로 실행 전 창/프레임 문맥으로 복구합니다.
- 시나리오 JSON에서 `leave_context: true`를 지정한 경우에만 마지막 창/프레임 문맥을 유지합니다.
- 결과 row에는 `frame_path`, `window_handle`, `window_title`, `window_url`, `tag`, `count`, `error_type`을 포함합니다.

## 4-2. XPath 안전 생성/Playwright 스캔
- XPath 문자열은 `xpath_explorer/tools/xpath_safety.py`의 `xpath_literal`, `xpath_attr_equals`, `xpath_contains_text`를 우선 사용합니다.
- AI fallback, Optimizer, Playwright scan, Selenium picker는 따옴표가 섞인 id/name/class/data/text 값을 invalid XPath로 만들지 않아야 합니다.
- Playwright scan 범위는 현재 프레임, 현재 창 전체 프레임, 모든 팝업/프레임입니다.
- Playwright scan으로 편집기에 로드한 항목은 Playwright 창/프레임 출처만 저장하고 Selenium의 stale frame으로 덮어쓰지 않습니다.
- Playwright page close fallback 후 `is_alive()`는 열린 fallback page를 즉시 재검증합니다.

## 5. 히스토리 정책
- `HistoryManager`는 Undo/Redo 스냅샷에서 `alternatives`, `screenshot_path`를 보존합니다.
- `element_attributes`는 최대 64개 키만 저장해 메모리 사용량 폭증을 방지합니다.

## 6. 저장 경로 정책
공통 경로 유틸은 `xpath_explorer/core/paths.py`를 사용합니다.
우선순위는 다음과 같습니다.
1. `Path.home()/.xpath_explorer`
2. `tempfile.gettempdir()/.xpath_explorer`
3. 둘 다 실패 시 in-memory only

적용 대상:
- 통계 파일(`statistics.json`)
- 디버그 로그(`debug.log`)
- AI 설정(`ai_config.json`)

AI 설정 저장 정책:
- `XPathAIAssistant.configure()`는 `ok/config_saved/storage_source/message` 결과를 반환합니다.
- 저장 경로가 없어도 유효한 설정은 현재 세션에 적용되며, UI는 저장 성공과 세션 전용 적용을 구분해 표시합니다.
- OpenAI 앱 기본 모델은 `gpt-5.4`, Gemini 기본 모델은 `gemini-flash-latest`입니다.

## 7. 운영 디버깅 체크리스트
- 브라우저 연결 실패: `browser.py`의 `is_alive`, `_recover_to_available_window` 로그 확인
- 세션 미스 오탐: `validate_xpath()`의 TTL/프레임 시그니처 갱신 로직 확인
- DOM diff 이상: `tools_mixin.py`에서 baseline source 불일치 시 baseline 재설정 동작 확인
- 저장 실패: `core/paths.py` 폴백 경로와 in-memory 모드 경고 확인
- Playwright scan 출처 이상: `ScannedElement.frame_path/window_*` 값과 저장 시 `_editing_source_engine` 확인
- 배치 결과 누락: `BatchTestWorker.item_validated`의 full result dict 전달과 UI `_record_validation_outcome` 입력 확인

## 8. 배포/품질 절차
개발 표준 설치:
`python -m venv .venv && .\.venv\Scripts\python.exe -m pip install -r requirements/requirements-dev.txt`

풀 기능 배포 빌드(선택 기능 포함) 시:
`.\.venv\Scripts\python.exe -m pip install -r requirements/requirements-full.txt`

### 로컬 필수 체크
1. `python scripts/check_docs_sync.py --strict-warnings`
2. `python scripts/check_encoding_health.py`
3. `python -m pyright -p .`
4. `pytest -q`
5. `python scripts/run_quality_checks.py --strict-doc-warnings --smoke-release`

### CI 게이트
- 워크플로: `.github/workflows/quality.yml`
- 실행 순서: `check_encoding_health` -> `pyright`
- 트리거: PR, `main`/`master` push
- GitHub Actions에서는 `pytest`를 실행하지 않음
- 테스트는 로컬/GUI 환경에서 수동 실행

보조 메모:
- `pytest`는 기본적으로 repo-local temp 경로(`.pytest_tmp/`)를 사용합니다.
- `run_quality_checks.py`는 `pytest-cov`가 없으면 plain `pytest`로 자동 폴백합니다.
- 커버리지가 필요 없으면 `python scripts/run_quality_checks.py --no-cov` 사용

### 릴리즈 스모크
`python scripts/run_release_smoke_checks.py`
- PyInstaller spec TLS exclude 회귀 검사
- HTTPS smoke (`https://example.com`)
- DOM report 렌더 smoke
- 선택 의존성 import 점검(openai/google-genai/playwright)

## 9. 패키징 메모
- spec 파일: `packaging/pyinstaller/xpath_explorer.spec`
- 엔트리포인트 후보: `xpath 조사기(모든 티켓 사이트).py`, `xpath_explorer/__main__.py`
- TLS 관련 라이브러리(`libcrypto`, `libssl`)는 exclude에 넣지 않습니다.
- 변경 후 반드시 release smoke 스크립트로 회귀 확인합니다.
- `hiddenimports`는 `collect_submodules("xpath_explorer")` 기반으로 수집합니다.
- `xpath_explorer.qt_compat`는 PyInstaller hidden import에 명시해 headless-safe bootstrap 경로를 유지합니다.
- split internals(`app/`, `ai/`, `ui/components/`, `ui/theme/`, `core/browser_assets/`, `browser/playwright_parts/`, `browser/selenium_validation_parts/`, `mixins/tools/batch/`, `mixins/tools/inspection/`)는 spec의 명시 hidden import와 `collect_submodules`로 함께 수집합니다.
- `openai`/`google.genai`/`playwright` 계열은 빌드 환경에 설치된 경우에만 포함됩니다.

## 10. 문서 동기화 원칙
- 구조/명칭은 실제 코드 경로 기준으로 작성
- 새 모듈/스크립트가 추가되면 `README.md`, `docs/claude.md`, `docs/gemini.md`를 함께 갱신
- 로컬 인덱스 `.codegraph/`는 `.gitignore`에 남겨 publish 대상에서 제외
- docs sync 실패를 릴리즈 차단 신호로 취급

## 11. Git 운영 체크
1. 코드 변경 후 `python scripts/check_docs_sync.py --strict-warnings` 실행
2. `python scripts/check_encoding_health.py` 실행
3. `python -m pyright -p .` 실행
4. `pytest -q` 실행
5. `python scripts/run_quality_checks.py --strict-doc-warnings --smoke-release` 실행
6. `.gitignore`에 신규 생성 산출물(로그/리포트/빌드 캐시) 누락이 없는지 확인
   - atomic JSON 저장 백업/임시 파일(`*.json.bak`, `.*.tmp`)은 로컬 산출물로 제외합니다.

## 12. Pylance/인코딩 운영 기준
- 인코딩 강제: `.editorconfig`에서 `charset = utf-8`
- VS Code 고정: `.vscode/settings.json`에서 `files.encoding = utf8`, `files.autoGuessEncoding = false`
- pyright 범위/진단: `pyrightconfig.json` 기준(`typeCheckingMode = basic`, `pythonVersion = 3.10`, 현재 Python 인터프리터 기준, `reportMissingImports = none`, exclude에 `.pytest_tmp` 포함)
- Qt 타입은 `TYPE_CHECKING` 분리 또는 `xpath_explorer/qt_compat.py`를 통해 가져와 headless CI import와 충돌시키지 않습니다.
- optional dependency import는 `xpath_explorer/core/optional_imports.py` 헬퍼를 통해 처리합니다.
- 오염 검사: `scripts/check_encoding_health.py`로 UTF-8 strict decode + 모지바케 패턴 + Python 문자열/주석의 `??` 반복 패턴 점검
- `.pytest_tmp`, `htmlcov`는 인코딩 검사 제외 대상이며, Selenium split 파일의 한국어 모지바케 토큰은 검사 대상입니다.

## 13. 진단/내보내기
- 도구 메뉴의 기능 진단 리포트 저장은 Selenium/Playwright 상태, 현재 창/프레임, 저장 항목 문맥, 최근 검증 실패, telemetry 요약을 Markdown으로 저장합니다.
- 배치/시나리오 결과 다이얼로그는 CSV와 Markdown 저장 버튼을 제공합니다.
- 설정 JSON은 `schema_version`을 선택적으로 저장하며, 로드 시 오래된/잘못된 타입의 선택 필드를 정규화합니다.

## 14. 2026-05-03 구현 리스크 반영
- 전체 검증과 live preview는 실행 전 창/프레임 문맥을 저장하고 종료 시 복구해야 합니다.
- 설정 JSON import는 중복 이름, 빈 이름, 빈 XPath를 거부합니다.
- `XPathItem.source_engine`은 Playwright 스캔 출처를 보존하는 선택 필드입니다.
- 설정/통계/AI 설정 저장은 `atomic_write_json()` 기반으로 부분 기록을 방지합니다.
- Playwright page handle은 세션 내 안정적인 `pw-page-N` 형식을 사용하며, Selenium 검증에서는 Playwright pseudo handle을 직접 Selenium handle로 취급하지 않습니다.
- GitHub Actions의 pytest 추가는 보류하며, 로컬 품질 절차에서 `pytest -q`, `python -m pyright -p .`, docs sync를 실행합니다.
- 임시 구현 리스크 점검 문서는 삭제하고 README/docs 운영 문서에 최종 정책만 유지합니다.
