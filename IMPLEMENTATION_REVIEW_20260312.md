# 기능 구현 점검 리포트 (2026-03-12)

## 점검 범위
- 기준 문서: `README.md`, `docs/claude.md`
- 핵심 구현: `xpath_explorer/browser/*`, `xpath_explorer/mixins/*`, `xpath_explorer/workers/background.py`, `xpath_explorer/core/config.py`, `xpath_explorer/analysis/statistics.py`
- 실행 점검:
  - `python scripts/check_docs_sync.py --strict-warnings`
  - `python scripts/check_encoding_health.py`
  - `pytest -q`
  - `python scripts/run_quality_checks.py --strict-doc-warnings`
- 결과 요약:
  - 문서/인코딩 정합성: 통과
  - 테스트: `70 passed`
  - 타입체크(`pyright`): 로컬 미설치로 미실행

## 잠재 문제 (기능 관점)

### 1) [높음] Python 내보내기 코드가 유효하지 않을 수 있음
- 근거: `xpath_explorer/mixins/data_mixin.py:478-484`
- 현상:
  - `safe_name = item.name.replace(' ', '_').upper()`만 사용해 Python 식별자 규칙을 보장하지 못함
  - 예: 이름이 `1-login.btn`이면 생성 코드가 문법 오류
  - 대소문자/특수문자 정규화 충돌 시 상수명이 덮어써질 수 있음
- 권장:
  - `CodeGenerator._safe_var_name()` 수준의 정규화 + 중복 시 suffix 부여
  - 내보내기 직후 `compile()` 기반 유효성 검사 추가

### 2) [높음] 항목 저장 시 “이름 변경” 충돌 처리 부재
- 근거: `xpath_explorer/mixins/data_mixin.py:324`, `xpath_explorer/mixins/data_mixin.py:371`, `xpath_explorer/core/config.py:180-190`
- 현상:
  - 저장 로직이 “현재 입력된 이름”만 기준으로 기존 항목을 판단
  - 편집 중 이름을 기존 다른 항목명으로 바꾸면 의도치 않은 덮어쓰기/중복 상태가 발생 가능
- 권장:
  - 편집 시작 시 원본 이름(`editing_original_name`) 추적
  - rename 충돌 시 사용자 확인(merge/replace/cancel) 단계 추가

### 3) [중간] Playwright 시작 성공 UI가 실제 이동 실패를 반영하지 않음
- 근거: `xpath_explorer/mixins/tools_mixin.py:1209-1215`, `xpath_explorer/mixins/tools_mixin.py:1231-1238`
- 현상:
  - `launch()` 성공 후 `navigate()` 결과(`True/None/False`)를 확인하지 않고 연결 성공으로 표시
  - 실제 URL 이동 실패/타임아웃이어도 사용자는 정상 연결로 인식
- 권장:
  - `navigate()` 반환값 분기 처리
  - `None`(타임아웃)와 `False`(실패) 구분 토스트/상태 메시지 제공

### 4) [중간] Playwright Chromium 설치가 UI 스레드를 블로킹함
- 근거: `xpath_explorer/mixins/tools_mixin.py:1230`, `xpath_explorer/browser/playwright.py:132-137`
- 현상:
  - `playwright install chromium`를 동기 실행해 수십 초~수분 UI 멈춤 가능
- 권장:
  - 설치를 워커 스레드로 분리하고 진행 상태/취소 UI 제공

### 5) [중간] 잘못된 XPath 문법 오류가 “요소 없음”으로 뭉개짐
- 근거: `xpath_explorer/browser/browser.py:730-747`, `xpath_explorer/browser/browser.py:1368-1371`
- 현상:
  - 프레임 탐색 중 예외를 모두 `None` 처리해 `InvalidSelector`도 “요소 없음”으로 반환될 수 있음
  - 디버깅/운영 시 원인 파악이 어려움
- 권장:
  - `InvalidSelectorException` 등은 별도 코드/메시지로 상위 전달
  - 결과 payload에 `error_type` 추가

### 6) [중간] 쿠키 로드 성공 개수가 실제 적용 수와 다를 수 있음
- 근거: `xpath_explorer/mixins/data_mixin.py:748-753`
- 현상:
  - 개별 `add_cookie` 실패를 모두 무시하고 전체 개수를 성공으로 표시
  - 도메인 불일치 상황에서 사용자 오인 가능
- 권장:
  - 성공/실패 카운트 분리 표기
  - 실패 원인 상위 N개 요약 제공

### 7) [중간] 히스토리 설정값 타입 가드 부족
- 근거: `xpath_explorer/mixins/data_mixin.py:650-651`, `xpath_explorer/mixins/data_mixin.py:638-640`
- 현상:
  - `QSettings` 값이 비정상 타입일 때(문자열/단일 dict) 리스트 전제 로직에서 오류 가능
- 권장:
  - 로드시 `list[dict]` 강제 정규화(`isinstance` 검사 + fallback `[]`)

### 8) [중간] 워커 종료 타임아웃 후 잔존 스레드 가능성
- 근거: `xpath_explorer/mixins/tools_mixin.py:1916-1919`, `xpath_explorer/mixins/tools_mixin.py:1935-1941`
- 현상:
  - `wait(timeout)` 실패 시 경고만 남기고 종료 진행
  - 종료 직후 늦은 signal emit으로 UI teardown race 가능
- 권장:
  - 타임아웃 시 signal disconnect + 안전한 강제 종료 경로(최후 수단) 추가

## 추가로 필요한 보강 항목

### A) 테스트 보강 (우선)
- 저장/이름변경 충돌 케이스 테스트
- `_export(fmt='python')` 식별자/중복 충돌 테스트
- Playwright 토글 시 `navigate()` 실패/타임아웃 UI 상태 테스트
- 쿠키 로드 성공/실패 집계 테스트
- invalid XPath 문법 오류 전파 테스트

### B) 품질 게이트 보강
- 근거: `scripts/run_quality_checks.py:19-68`
- 제안:
  - 문서에 명시된 `pyright`를 품질 스크립트 옵션으로 포함
  - CI에서 “문서 sync + pytest + type check”를 기본 게이트로 통합

## 결론
- 현재 기준선에서는 테스트/문서 정합성은 안정적입니다.
- 다만 실제 사용자 플로우(저장 충돌, Playwright 시작/설치 UX, 오류 메시지 분해, 쿠키 로딩 정확도)에서 운영 이슈로 번질 수 있는 지점이 확인되었습니다.
- 위 8개 항목 중 1~4번을 우선 처리하면 체감 장애 가능성을 크게 줄일 수 있습니다.

## 후속 반영 현황 (2026-03-12)
- 본 리포트의 8개 항목은 코드/테스트에 반영되었습니다.
- Pylance 재발 방지를 위해 optional import 헬퍼(`xpath_explorer/core/optional_imports.py`)를 도입했습니다.
- 로컬/CI 품질 게이트를 일치시켰습니다.
  - 로컬: `python scripts/run_quality_checks.py --with-pyright`
  - CI: `.github/workflows/quality.yml` (`check_encoding_health` -> `pyright` -> `pytest -q`)
- 인코딩 점검 규칙을 강화했습니다(`scripts/check_encoding_health.py`).
- PyInstaller spec은 optional third-party 모듈을 “설치된 경우에만” `hiddenimports`에 포함하도록 보강했습니다.
