# XPath Explorer 기능 구현 점검 리포트

- 점검 일시: 2026-02-28
- 기준 문서: `README.md`, `docs/claude.md`
- 점검 범위: `xpath_explorer/` 구현 코드, `scripts/check_docs_sync.py`, 테스트 구성

## 핵심 결론

현재 테스트(`45 passed`) 기준으로 기본 회귀는 안정적입니다. 다만 운영 시 장애/오판 가능성을 높이는 구현 리스크가 몇 가지 있으며, 문서-코드 정합성 체크 범위가 약해져 향후 유지보수 비용이 커질 가능성이 있습니다.

## 주요 발견 사항 (Severity 순)

### 1) [High] Playwright 초기화 실패 시 부분 생성 리소스 정리가 누락될 수 있음
- 위치: `xpath_explorer/browser/playwright.py:241`
- 근거: `launch()`의 `except` 경로가 `last_error` 설정 후 `return False`만 수행하며, `_playwright/_browser/_context/_page` 부분 생성 상태를 정리하지 않음.
- 영향: 특정 실패 케이스에서 백그라운드 프로세스/핸들 누수, 다음 실행 시 비정상 상태 재진입 가능.
- 권장 조치:
  - `launch()`의 예외 블록에서 `self.close()`를 호출하거나, 단계별 생성 성공분만 정리하는 `_cleanup_partial_launch()` 추가.
  - 재현 테스트 추가: `new_context` 강제 예외 시 리소스가 모두 `None`으로 복구되는지 검증.

### 2) [Medium] 시나리오 실행 UI가 실패율과 무관하게 성공 토스트를 표시
- 위치: `xpath_explorer/mixins/tools_mixin.py:244`, `:250`
- 근거: `on_completed()`에서 `toast_type = "warning" if cancelled else "success"`로 고정되어, `cancelled=False`면 실패가 많아도 성공 토스트 처리.
- 영향: 운영자가 실패가 많은 실행을 성공으로 오인할 수 있음.
- 권장 조치:
  - `success_count < total`이면 `warning` 또는 `error` 토스트로 분기.
  - 결과 라벨에 실패율 임계치(예: 80% 미만 경고) 반영.

### 3) [Medium] BatchScenarioWorker에 명시적 실패 시그널/상위 예외 보고 경로가 없음
- 위치: `xpath_explorer/workers/background.py:351-353`, `:436-541`
- 근거: `BatchScenarioWorker`는 `progress/step_completed/completed`만 있고, `run()` 상위 예외를 UI로 전달하는 `failed` 시그널이 없음.
- 영향: 예기치 않은 예외 발생 시 UI가 조용히 종료되거나 원인 파악이 늦어질 가능성.
- 권장 조치:
  - `failed = pyqtSignal(str)` 추가.
  - `run()`에 `except Exception as e` 추가 후 `failed.emit(str(e))`, UI에서 에러 토스트+요약 출력.

### 4) [Medium] 설정 저장 훅이 미구현 상태
- 위치: `xpath_explorer/mixins/tools_mixin.py:1741-1744`
- 근거: `_save_settings()`가 `pass` 상태.
- 영향: 현재는 `geometry`만 저장되고, 향후 UI 옵션(필터/패널 상태/사용자 기본값) 확장 시 저장 누락 가능.
- 권장 조치:
  - 최소 MVP: `font_size`, 최근 탭, URL 패널 접힘 상태, 마지막 프리셋 등을 저장/복원.
  - `_load_settings()`(data_mixin)와 키 스키마를 명시적으로 맞추기.

### 5) [Medium] 문서 정합성 체크가 README 중심으로 축소되어 드리프트 탐지가 약화됨
- 위치: `scripts/check_docs_sync.py:34`, `:96`
- 근거: `REQUIRED_DOC_FILES`에는 `docs/claude.md`, `docs/gemini.md`가 포함되지만, `REQUIRED_TOKENS` 검증은 `README.md`만 수행.
- 영향: Claude/Gemini 운영 문서가 코드 구조와 어긋나도 CI/로컬 체크에서 탐지되지 않음.
- 권장 조치:
  - `docs/claude.md`, `docs/gemini.md`에도 핵심 경로 토큰 검증 재추가.
  - 최소 토큰: `xpath_explorer/browser/browser.py`, `xpath_explorer/tools/ai.py`, `xpath_explorer/workers/background.py`.

### 6) [Low] docs/claude.md는 일부 경로가 레거시 파일명 기준으로 남아 있음
- 위치 예시: `docs/claude.md:33-38` (`xpath_browser.py`, `xpath_workers.py` 등)
- 기준 문서 대비: `README.md`는 기능별 패키지 경로(`xpath_explorer/...`)로 갱신됨.
- 영향: 신규 기여자가 수정 지점을 오인할 가능성.
- 권장 조치:
  - `docs/claude.md`의 파일 참조를 패키지 경로로 통일.
  - “레거시 파일/경로” 섹션을 별도 분리해 혼선을 줄이기.

### 7) [Low] 로거 초기화가 홈 디렉토리 쓰기 실패를 직접 처리하지 않음
- 위치: `xpath_explorer/runtime.py:176-179`
- 근거: `Path.home()/.xpath_explorer` 생성 및 `FileHandler` 생성에서 예외 핸들링 없음.
- 영향: 제한된 실행 환경(읽기 전용 홈/권한 제한)에서 앱 시작 실패 가능.
- 권장 조치:
  - 파일 핸들러 생성 실패 시 콘솔 핸들러만 유지하는 폴백 경로 추가.

### 8) [Low] 텔레메트리 Markdown 렌더링 시 메시지 escaping 부재
- 위치: `xpath_explorer/runtime.py:126`, `:143`
- 근거: 메시지를 표 셀에 그대로 삽입(`|`)하여 보고서 포맷 깨짐 가능.
- 영향: 장애 리포트 가독성 저하.
- 권장 조치:
  - `|`, 줄바꿈, 백틱 최소 escape 처리 유틸 적용.

## 추가 구현 권장 사항

1. 시나리오 실행 품질 지표 강화
- 실패율 임계치 경고, 스텝별 재시도 횟수/총 재시도 요약 추가.

2. “실패 원인 우선” 리포트 템플릿
- 배치/시나리오 완료 후 상위 실패 원인 Top N을 자동 요약(현재 error telemetry와 연동).

3. 문서/코드 정합성 체크 계층화
- README(공개 문서) / docs(운영 문서) / tests(검증 시나리오)별 필수 토큰을 분리 관리.

4. 런치/종료 시나리오 회귀 테스트 보강
- `PlaywrightManager.launch()` 실패 복구, `closeEvent()` 워커 종료 타임아웃, 로거 폴백 경로 테스트 추가.

## 검증 메모

- 실행한 검증:
  - `pytest -q` -> `45 passed`
- 참고:
  - 본 리포트는 코드/문서 정합성 및 실패 경로 중심의 정적 점검 결과입니다.
