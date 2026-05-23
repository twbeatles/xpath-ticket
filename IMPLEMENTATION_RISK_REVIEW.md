# Implementation Risk Review

검토일: 2026-05-23

참조 문서: `README.md`, `docs/claude.md`, `docs/gemini.md`, `docs/PROJECT_STRUCTURE_ANALYSIS.md`

## 반영 상태

이 문서의 기능 구현 리스크와 개선 제안은 2026-05-23 작업에서 모두 코드, 테스트, 문서, CI 설정에 반영했다. 아래 항목은 최초 검토 관점과 최종 조치 내역을 함께 남긴 것이다.

## 주요 리스크와 조치

### 1. AI 키 저장과 페이지 컨텍스트 노출

- 리스크: AI API 키가 평문 설정으로 저장될 수 있고, DOM/속성 컨텍스트가 외부 AI 요청에 과도하게 포함될 수 있었다.
- 조치: `keyring`, `session`, `env`, `plain` 저장 정책을 분리하고 기본값에서 평문 저장을 피하도록 했다.
- 조치: `XPATH_EXPLORER_AI_KEY_STORAGE`, `XPATH_EXPLORER_AI_ALLOW_PAGE_CONTEXT` 환경 제어를 추가했다.
- 조치: 민감 속성 redaction을 보강하고, 페이지 컨텍스트 전송은 명시 opt-in으로 제한했다.
- 검증: AI 설정 우선순위, fallback, 민감 정보 escape 테스트를 추가했다.

### 2. 생성 코드의 window/frame 컨텍스트 재현성

- 리스크: Selenium/Playwright 코드 생성 결과가 수집 당시의 window/frame 컨텍스트를 충분히 복원하지 못하면, 재실행 시 다른 요소를 찾거나 실패할 수 있었다.
- 조치: 생성 코드에 `ITEM_CONTEXTS` 메타데이터와 window/frame 전환 로직을 포함했다.
- 조치: Selenium과 Playwright 템플릿 모두 컨텍스트별 locator 실행 흐름을 갖도록 보강했다.
- 검증: 코드 생성 템플릿 테스트를 확장했다.

### 3. CSV/스프레드시트 Formula Injection

- 리스크: 내보낸 CSV 셀이 `=`, `+`, `-`, `@` 등으로 시작할 경우 스프레드시트에서 수식으로 실행될 수 있었다.
- 조치: `xpath_explorer/tools/csv_safety.py`를 추가하고 파일/배치 export 경로에 적용했다.
- 검증: DOM export, batch report export, data mixin 테스트를 추가했다.

### 4. Selenium frame/window 상태 복원

- 리스크: frame 탐색이나 window 목록 수집 후 원래 브라우저 컨텍스트가 복원되지 않으면 이후 작업이 다른 frame에서 실행될 수 있었다.
- 조치: frame/window helper가 원래 window와 frame chain을 복원하도록 수정했다.
- 검증: Selenium frame restore 테스트를 추가했다.

### 5. Playwright Chromium 설치 흐름

- 리스크: 패키징된 실행 파일 환경에서 `playwright install chromium` 호출 경로가 깨지거나 설치 취소 이벤트가 즉시 반영되지 않을 수 있었다.
- 조치: 외부 CLI, 현재 Python의 `-m playwright`, bundled `playwright.__main__` 순서로 설치 경로를 시도하도록 보강했다.
- 조치: 설치 subprocess를 cancellable하게 만들고 PyInstaller hidden import를 추가했다.
- 검증: Playwright install 경로 테스트를 추가했다.

### 6. CI와 릴리스 스모크 커버리지

- 리스크: 로컬 품질 스크립트와 GitHub Actions 검증 범위가 달라 릴리스 직전 회귀가 늦게 발견될 수 있었다.
- 조치: CI에 encoding health, strict docs sync, pyright, pytest 순서를 명시했다.
- 조치: `run_quality_checks.py`에 `--strict-optional-imports`, `--build-exe` 전달 옵션을 추가했다.
- 조치: `run_release_smoke_checks.py`에 선택적 PyInstaller build smoke를 추가했다.
- 검증: 품질 스크립트와 릴리스 스모크 테스트를 추가했다.

### 7. 의존성 범위와 optional import 정책

- 리스크: 버전 미고정 의존성으로 설치 재현성이 낮고, optional dependency 누락이 릴리스 시점에 늦게 발견될 수 있었다.
- 조치: `requirements/*.txt`에 상한 범위를 추가하고 full profile에 `keyring`을 포함했다.
- 조치: optional import 검증을 strict 모드에서 실패로 승격할 수 있게 했다.

### 8. 인코딩 가드와 문서 동기화

- 리스크: 한글 주석/문서에서 mojibake가 재발할 수 있고, README와 agent 문서의 품질 명령이 어긋날 수 있었다.
- 조치: Korean mojibake 탐지 토큰을 보강하고 깨진 주석을 수정했다.
- 조치: README, Claude, Gemini, 구조 분석 문서에 새 보안/품질 정책을 반영했다.

## 최종 검증

다음 검증을 통과했다.

- `python scripts\check_docs_sync.py --strict-warnings`
- `python scripts\check_encoding_health.py`
- `python -m pyright -p .`
- `pytest -q`
- `python scripts\run_release_smoke_checks.py`
- `python scripts\run_quality_checks.py --strict-doc-warnings --smoke-release --no-cov`
- `git diff --check`

참고: 현재 환경에는 `ruff` 실행 파일이 설치되어 있지 않아 `python -m ruff check .`는 별도 검증에서 제외했다.
