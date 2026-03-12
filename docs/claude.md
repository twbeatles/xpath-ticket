# Claude 운영 가이드 (XPath Explorer)

## 1. 프로젝트 개요
XPath Explorer는 Selenium/Playwright 기반으로 XPath를 수집·검증·분석하는 데스크톱 도구입니다.
핵심 실행 진입점은 `xpath_explorer/main_window.py`이며, 화면/브라우저/데이터/도구 책임을 mixin으로 분리했습니다.

## 2. 현재 코드 구조
- UI 조립: `xpath_explorer/main_window.py`
- UI 동작: `xpath_explorer/mixins/ui_mixin.py`
- 브라우저 제어: `xpath_explorer/mixins/browser_mixin.py`
- 데이터/설정 관리: `xpath_explorer/mixins/data_mixin.py`
- 고급 기능(배치/리포트/도구): `xpath_explorer/mixins/tools_mixin.py`
- Selenium 핵심 매니저: `xpath_explorer/browser/browser.py`
- Playwright 매니저: `xpath_explorer/browser/playwright.py`
- DOM 리포트 렌더러: `xpath_explorer/browser/dom_export.py`
- 백그라운드 워커: `xpath_explorer/workers/background.py`
- AI 어시스턴트: `xpath_explorer/tools/ai.py`
- 통계/분석: `xpath_explorer/analysis/statistics.py`, `xpath_explorer/analysis/diff.py`
- 런타임 로깅/텔레메트리: `xpath_explorer/runtime.py`

## 3. 핵심 실행 흐름
1. `main_window.py`에서 Qt 환경 변수 설정 후 `QApplication` 생성
2. `XPathExplorer` 초기화 시 Browser/History/Stats/AI 모듈 결합
3. 사용자 액션에 따라 워커(`background.py`)가 비동기 검증 수행
4. 검증 결과를 통계/히스토리/테이블 모델에 반영
5. 필요 시 DOM export/diff 리포트 생성

## 4. 검증 세션/프레임 전략
- `xpath_explorer/browser/browser.py`의 `begin_validation_session()`은 프레임 목록/힌트/미스 캐시를 세션 단위로 유지합니다.
- 미스 캐시는 TTL 기반(`VALIDATION_MISS_TTL_SECONDS`)이며 프레임 시그니처가 바뀌면 무효화합니다.
- 배치 검증 워커는 동일 세션을 재사용해 중복 스캔을 줄입니다.

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

## 7. 운영 디버깅 체크리스트
- 브라우저 연결 실패: `browser.py`의 `is_alive`, `_recover_to_available_window` 로그 확인
- 세션 미스 오탐: `validate_xpath()`의 TTL/프레임 시그니처 갱신 로직 확인
- DOM diff 이상: `tools_mixin.py`에서 baseline source 불일치 시 baseline 재설정 동작 확인
- 저장 실패: `core/paths.py` 폴백 경로와 in-memory 모드 경고 확인

## 8. 배포/품질 절차
개발 표준 설치:
`pip install -r requirements/requirements-dev.txt`

풀 기능 배포 빌드(선택 기능 포함) 시:
`pip install -r requirements/requirements-full.txt`

### 로컬 필수 체크
1. `python scripts/check_docs_sync.py --strict-warnings`
2. `python scripts/check_encoding_health.py`
3. `pyright xpath_explorer tests scripts "xpath 조사기(모든 티켓 사이트).py"` (없으면 `python -m pyright ...`)
4. `pytest -q`
5. `python scripts/run_quality_checks.py --strict-doc-warnings --smoke-release`

### CI 게이트
- 워크플로: `.github/workflows/quality.yml`
- 실행 순서: `check_encoding_health` -> `pyright` -> `pytest -q`
- 트리거: PR, `main`/`master` push

### 릴리즈 스모크
`python scripts/run_release_smoke_checks.py`
- PyInstaller spec TLS exclude 회귀 검사
- HTTPS smoke (`https://example.com`)
- DOM report 렌더 smoke
- 선택 의존성 import 점검(openai/google-genai/playwright)

## 9. 패키징 메모
- spec 파일: `packaging/pyinstaller/xpath_explorer.spec`
- TLS 관련 라이브러리(`libcrypto`, `libssl`)는 exclude에 넣지 않습니다.
- 변경 후 반드시 release smoke 스크립트로 회귀 확인합니다.
- `hiddenimports`는 `collect_submodules("xpath_explorer")` 기반으로 수집합니다.
- `openai`/`google.genai`/`playwright` 계열은 빌드 환경에 설치된 경우에만 포함됩니다.

## 10. 문서 동기화 원칙
- 구조/명칭은 실제 코드 경로 기준으로 작성
- 새 모듈/스크립트가 추가되면 `README.md`, `docs/claude.md`, `docs/gemini.md`를 함께 갱신
- docs sync 실패를 릴리즈 차단 신호로 취급

## 11. Git 운영 체크
1. 코드 변경 후 `python scripts/check_docs_sync.py --strict-warnings` 실행
2. `python scripts/check_encoding_health.py` 실행
3. `pyright xpath_explorer tests scripts "xpath 조사기(모든 티켓 사이트).py"` 실행 (없으면 `python -m pyright ...`)
4. `pytest -q` 실행
5. `python scripts/run_quality_checks.py --strict-doc-warnings --smoke-release` 실행
6. `.gitignore`에 신규 생성 산출물(로그/리포트/빌드 캐시) 누락이 없는지 확인

## 12. Pylance/인코딩 운영 기준
- 인코딩 강제: `.editorconfig`에서 `charset = utf-8`
- VS Code 고정: `.vscode/settings.json`에서 `files.encoding = utf8`, `files.autoGuessEncoding = false`
- pyright 범위/진단: `pyrightconfig.json` 기준(`typeCheckingMode = basic`, `pythonVersion = 3.10`)
- optional dependency import는 `xpath_explorer/core/optional_imports.py` 헬퍼를 통해 처리합니다.
- 오염 검사: `scripts/check_encoding_health.py`로 UTF-8 strict decode + 모지바케 패턴 + Python 문자열/주석의 `??` 반복 패턴 점검
