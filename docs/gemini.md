# Gemini 운영 가이드 (XPath Explorer)

## 목적
이 문서는 Gemini 기반 보조 자동화를 포함한 XPath Explorer 운영·유지보수 기준을 정의합니다.
구현 실제와 문서를 항상 동기화하는 것이 목표입니다.

## 아키텍처 요약
- 메인 조립: `xpath_explorer/main_window.py`
- Selenium 제어: `xpath_explorer/browser/browser.py`
- 워커 실행: `xpath_explorer/workers/background.py`
- AI 제안: `xpath_explorer/tools/ai.py`
- 통계 기록: `xpath_explorer/analysis/statistics.py`
- 경로 폴백 유틸: `xpath_explorer/core/paths.py`

## 기능 모듈 책임
- `browser.py`: 윈도우/프레임 복구, XPath 검증, 세션 캐시(힌트/미스)
- `background.py`: Validate/Batch/Scenario 워커 및 취소 처리
- `ai.py`: OpenAI·Gemini provider 선택, 설정 로드/저장
- `statistics.py`: 비동기 flush 기반 테스트 통계 누적
- `tools_mixin.py`: DOM export/diff, 배치 리포트, 히스토리 UI 연계

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

4. DOM diff 안전성
- 기준선 소스(Selenium/Playwright)와 현재 소스가 다르면 비교 대신 baseline 재설정

5. Qt 환경 변수 순서
- `configure_qt_env()`를 통해 `QApplication` 생성 전에 환경 변수 적용

## 디버깅 포인트
- 반복적인 not found: `browser.py`의 세션 miss TTL/시그니처 갱신 여부 확인
- 배치 워커 결과 일관성: `background.py`에서 session 재사용 확인
- 로그 파일 미생성: `runtime.py` + `core/paths.py` 폴백 결과 확인
- AI 설정 저장 누락: `ai.py`에서 저장 경로 resolve 실패 경고 확인

## 테스트/검증 루틴
1. 개발/배포 환경 설치
- 개발 표준: `pip install -r requirements/requirements-dev.txt`
- 풀 기능 배포 빌드: `pip install -r requirements/requirements-full.txt`

2. 문서 동기화
- `python scripts/check_docs_sync.py --strict-warnings`

3. 인코딩/타입 점검
- `python scripts/check_encoding_health.py`
- `pyright xpath_explorer tests scripts "xpath 조사기(모든 티켓 사이트).py"`
- `pyright` 명령이 없으면 `python -m pyright ...` 사용

4. 회귀 테스트
- `pytest -q`

5. 릴리즈 사전 점검
- `python scripts/run_quality_checks.py --strict-doc-warnings --smoke-release`
- 내부적으로 `scripts/run_release_smoke_checks.py`를 호출

6. CI 게이트 확인
- 워크플로: `.github/workflows/quality.yml`
- 순서: `check_encoding_health` -> `pyright` -> `pytest -q`
- 트리거: PR, `main`/`master` push

## 배포 체크리스트
- `packaging/pyinstaller/xpath_explorer.spec`에서 TLS 관련 exclude 회귀 확인
- `collect_submodules("xpath_explorer")` 기반 수집 확인
- `openai`/`google.genai`/`playwright` optional hidden import는 설치된 환경에서만 포함되는지 확인
- HTTPS smoke 성공 확인
- DOM report/diff 렌더 smoke 성공 확인
- 선택 의존성(import) 상태 확인(openai/google-genai/playwright)

## 문서 유지 규칙
- 파일 경로는 실제 코드 경로를 그대로 사용
- 기능 추가/변경 시 README + 본 문서 동시 갱신
- docs sync 경고도 릴리즈 전 반드시 해소

## Git 정리 규칙
1. `.gitignore`에 로컬 런타임 산출물(`.xpath_explorer/`, `htmlcov/`, PyInstaller 산출물) 누락 여부 점검
2. `python scripts/check_encoding_health.py` + `pyright xpath_explorer tests scripts "xpath 조사기(모든 티켓 사이트).py"` 점검 통과 후 커밋
3. 기본 브랜치(`main`) 푸시 전 테스트/문서 정합성 재확인

## Pylance/인코딩 고정 설정
- `.editorconfig`: 저장 인코딩 `utf-8` 강제
- `.vscode/settings.json`: `files.encoding=utf8`, `files.autoGuessEncoding=false`
- `pyrightconfig.json`: 분석 범위(`xpath_explorer/tests/scripts/entrypoint`)와 제외 경로(`archive`, 캐시/빌드) 고정
- optional dependency import는 `xpath_explorer/core/optional_imports.py` 헬퍼를 통해 처리
