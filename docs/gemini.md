# Gemini 운영 가이드 (XPath Explorer)

## 목적
이 문서는 Gemini 기반 보조 자동화를 포함한 XPath Explorer 운영·유지보수 기준을 정의합니다.
구현 실제와 문서를 항상 동기화하는 것이 목표입니다.

## 아키텍처 요약
- 패키지 진입점: `xpath_explorer/__main__.py`
- 메인 조립 facade: `xpath_explorer/main_window.py`
- 메인 조립 구현: `xpath_explorer/app/main_window.py`
- Qt 호환 계층: `xpath_explorer/qt_compat.py`
- Selenium facade: `xpath_explorer/browser/browser.py`
- Selenium internals: `xpath_explorer/browser/selenium_*.py`, `xpath_explorer/browser/selenium_validation_parts/`
- Playwright facade: `xpath_explorer/browser/playwright.py`
- Playwright internals: `xpath_explorer/browser/playwright_*.py`, `xpath_explorer/browser/playwright_parts/`
- 워커 facade: `xpath_explorer/workers/background.py`
- 워커 internals: `xpath_explorer/workers/*_worker.py`
- mixin facade: `xpath_explorer/mixins/ui_mixin.py`, `browser_mixin.py`, `data_mixin.py`, `tools_mixin.py`
- split mixin internals: `xpath_explorer/mixins/ui/`, `browser/`, `data/`, `tools/`, `tools/batch/`, `tools/inspection/`
- split mixin contracts/seams: `xpath_explorer/mixins/contracts.py`, `xpath_explorer/mixins/*/deps.py`
- AI facade: `xpath_explorer/tools/ai.py`
- AI internals: `xpath_explorer/ai/`
- UI internals: `xpath_explorer/ui/components/`, `xpath_explorer/ui/theme/`
- 통계 기록: `xpath_explorer/analysis/statistics.py`
- 경로 폴백 유틸: `xpath_explorer/core/paths.py`

## 기능 모듈 책임
- `browser.py`: Selenium facade
- `selenium_*.py`: 윈도우/프레임 복구, XPath 검증, 세션 캐시(힌트/미스)
- `background.py`: 워커 facade
- `*_worker.py`: Validate/Batch/Scenario 워커 및 취소 처리
- `tools/ai.py`: AI 호환 facade
- `ai/`: OpenAI·Gemini provider 선택, 설정 로드/저장, fallback/model helper
- `statistics.py`: 비동기 flush 기반 테스트 통계 누적
- `tools_mixin.py`: facade
- `mixins/tools/`: DOM export/diff, 배치 리포트, 히스토리 UI 연계 facade
- `mixins/tools/batch/`, `mixins/tools/inspection/`: 배치 runner/report와 진단/통계/DOM diff 세부 구현
- `mixins/contracts.py`, `mixins/*/deps.py`: split mixin 타입 계약 및 patch seam

## 팝업/DOM 운영 포인트
- 항목 스키마는 `found_window`, `found_window_title`, `found_window_url`, `found_frame`를 함께 저장합니다.
- 단건 검증/하이라이트/스크린샷은 명시적 창 선택이 없으면 항목에 저장된 창 문맥을 우선 사용합니다.
- Selenium 창 매핑 순서는 `handle -> exact URL -> exact title`입니다.
- DOM export는 `전체`, `현재 창`, `현재 창 + iframe` 범위로 분리되어 동작합니다.
- Playwright는 `_root_page`와 current page를 추적해 popup/page close 이후에도 page-scoped 기능을 복구합니다.
- 시나리오 워커는 `wait_for_popup`, `switch_latest_popup`, `switch_window_by_title`, `switch_root_window` 액션을 지원합니다.
- 배치/시나리오 실행 후 기본값은 원래 창/프레임 복구이며, 시나리오 JSON의 `leave_context: true`에서만 마지막 문맥을 유지합니다.
- 배치/시나리오 결과에는 `frame_path`, `window_handle`, `window_title`, `window_url`, `tag`, `count`, `error_type`을 포함합니다.
- Playwright scan은 현재 프레임, 현재 창 전체 프레임, 모든 팝업/프레임 범위를 지원하고 `ScannedElement`에 창/프레임 출처를 기록합니다.
- scan 결과를 저장할 때는 출처 엔진 기준으로만 문맥을 반영해 Playwright 출처가 Selenium stale frame으로 덮이지 않도록 합니다.

## XPath 안전 생성
- XPath 생성 시 `xpath_explorer/tools/xpath_safety.py`의 `xpath_literal`, `xpath_attr_equals`, `xpath_contains_text`를 사용합니다.
- AI fallback, Optimizer, Playwright scan, picker 경로는 id/name/class/data/text 값에 큰따옴표와 작은따옴표가 섞여도 valid XPath를 생성해야 합니다.

## 최근 운영 정책 반영 사항
1. Validation miss 캐시
- 미스는 TTL(`VALIDATION_MISS_TTL_SECONDS`) + frame_signature 조건에서만 재탐색 생략
- 프레임 시그니처 변경 시 기존 miss 캐시 즉시 무효화

2. 히스토리 스냅샷
- Undo/Redo에서 `alternatives`, `screenshot_path` 보존
- `element_attributes`는 최대 64개 키만 저장

3. 저장 경로 내성
- 1순위: 홈 디렉터리
- 2순위: 시스템 TEMP
- 실패 시: in-memory only (예외 없이 동작)
- AI 설정 저장은 `ok/config_saved/storage_source/message` 결과로 노출되며, 세션 전용 적용과 디스크 저장 성공을 구분합니다.
- OpenAI 앱 기본 모델은 `gpt-5.4`, Gemini 기본 모델은 `gemini-flash-latest`입니다.

4. DOM diff 안전성
- 기준선 소스(Selenium/Playwright)와 현재 소스가 다르면 비교 대신 baseline 재설정

5. Qt 환경 변수 순서
- `configure_qt_env()`를 통해 `QApplication` 생성 전에 환경 변수 적용

## 디버깅 포인트
- 반복적인 not found: `browser.py`의 세션 miss TTL/시그니처 갱신 여부 확인
- 배치 워커 결과 일관성: `background.py`에서 session 재사용 확인
- 배치 결과 메타데이터 누락: `BatchTestWorker.item_validated` full result dict와 UI 기록 경로 확인
- Playwright scan 문맥 이상: scan scope, `frame_path`, `window_title/url`, `_editing_source_engine` 저장 경로 확인
- 로그 파일 미생성: `runtime.py` + `core/paths.py` 폴백 결과 확인
- AI 설정 저장 누락: `ai.py`에서 저장 경로 resolve 실패 경고 확인

## 테스트/검증 루틴
1. 개발/배포 환경 설치
- 개발 표준: `python -m venv .venv && .\.venv\Scripts\python.exe -m pip install -r requirements/requirements-dev.txt`
- 풀 기능 배포 빌드: `.\.venv\Scripts\python.exe -m pip install -r requirements/requirements-full.txt`

2. 문서 동기화
- `python scripts/check_docs_sync.py --strict-warnings`

3. 인코딩/타입 점검
- `python scripts/check_encoding_health.py`
- `python -m pyright -p .`

4. 회귀 테스트
- `pytest -q`
- 기본 temp 경로는 repo-local `.pytest_tmp/`입니다.

5. 릴리즈 사전 점검
- `python scripts/run_quality_checks.py --strict-doc-warnings --smoke-release`
- 내부적으로 `scripts/run_release_smoke_checks.py`를 호출
- `pytest-cov`가 없으면 plain `pytest`로 자동 폴백합니다.
- 커버리지를 강제로 끄려면 `python scripts/run_quality_checks.py --no-cov`

6. CI 게이트 확인
- 워크플로: `.github/workflows/quality.yml`
- 순서: `check_encoding_health` -> `pyright`
- 트리거: PR, `main`/`master` push
- GitHub Actions에서는 `pytest`를 실행하지 않음
- 테스트는 로컬/GUI 환경에서 별도 확인

## 배포 체크리스트
- `packaging/pyinstaller/xpath_explorer.spec`에서 TLS 관련 exclude 회귀 확인
- 엔트리포인트 후보(`xpath 조사기(모든 티켓 사이트).py`, `xpath_explorer/__main__.py`) 유지 확인
- `collect_submodules("xpath_explorer")` 기반 수집 확인
- `xpath_explorer.qt_compat` hidden import 포함 확인
- split internals(`app/`, `ai/`, `ui/components/`, `ui/theme/`, `core/browser_assets/`, `browser/playwright_parts/`, `browser/selenium_validation_parts/`, `mixins/tools/batch/`, `mixins/tools/inspection/`) 명시 hidden import와 `collect_submodules` 수집 확인
- `openai`/`google.genai`/`playwright` optional hidden import는 설치된 환경에서만 포함되는지 확인
- HTTPS smoke 성공 확인
- DOM report/diff 렌더 smoke 성공 확인
- 선택 의존성(import) 상태 확인(openai/google-genai/playwright)

## 문서 유지 규칙
- 파일 경로는 실제 코드 경로를 그대로 사용
- 기능 추가/변경 시 README + 본 문서 동시 갱신
- docs sync 경고도 릴리즈 전 반드시 해소

## Git 정리 규칙
1. `.gitignore`에 로컬 런타임 산출물(`.xpath_explorer/`, `.pytest_tmp/`, `htmlcov/`, PyInstaller 산출물, atomic 저장 백업/임시 파일 `*.json.bak`, `.*.tmp`) 누락 여부 점검
2. `python scripts/check_encoding_health.py` + `python -m pyright -p .` 점검 통과 후 커밋
3. 기본 브랜치(`main`) 푸시 전 테스트/문서 정합성 재확인

## Pylance/인코딩 고정 설정
- `.editorconfig`: 저장 인코딩 `utf-8` 강제
- `.vscode/settings.json`: `files.encoding=utf8`, `files.autoGuessEncoding=false`
- `pyrightconfig.json`: 분석 범위(`xpath_explorer/tests/scripts/entrypoint`)와 제외 경로(`archive`, `.pytest_cache`, `.pytest_tmp`, 빌드 산출물) 고정, 현재 Python 인터프리터 기준 동작, `reportMissingImports = none`
- Qt 관련 타입은 `TYPE_CHECKING` import 분리 또는 `xpath_explorer/qt_compat.py`를 사용해 headless CI와 정적 분석을 함께 만족시킴
- optional dependency import는 `xpath_explorer/core/optional_imports.py` 헬퍼를 통해 처리
- `scripts/check_encoding_health.py`는 `.pytest_tmp`, `htmlcov`를 제외하고, Selenium split 파일의 한국어 모지바케 토큰과 Python 문자열/주석의 `??` 반복 패턴을 점검합니다.

## 진단/내보내기
- 도구 메뉴의 기능 진단 리포트는 Selenium/Playwright 상태, 현재 창/프레임, 저장 항목 문맥, 최근 검증 실패, telemetry 요약을 Markdown으로 저장합니다.
- 배치/시나리오 결과 다이얼로그는 CSV/Markdown 저장을 지원합니다.
- 설정 JSON은 `schema_version`을 선택적으로 저장하고, 로드 시 오래된/잘못된 선택 필드 타입을 정규화합니다.
- 2026-05-03 이후 설정 JSON import는 중복 이름, 빈 이름, 빈 XPath를 거부합니다.
- `XPathItem.source_engine`으로 Playwright 스캔 출처를 보존하며, Playwright page handle은 세션 내 안정적인 `pw-page-N` 형식을 사용합니다.
- 설정/통계/AI 설정 저장은 `atomic_write_json()` 기반으로 부분 기록을 방지합니다.
- CI pytest 추가는 보류하며, 회귀 테스트는 로컬 품질 절차에서 `pytest -q`로 확인합니다.
- 임시 구현 리스크 점검 문서는 삭제하고 README/docs 운영 문서에 최종 정책만 유지합니다.
