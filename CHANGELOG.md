# Changelog

## v4.4 - 2026-09-25

### 사용자 기능
- 편집기에 **클릭 테스트** 버튼을 추가했습니다. 입력된 XPath 요소를 실제 브라우저에서 직접 클릭해 보고, 실패 시 원인을 결과창에 표시합니다 (Selenium 스크롤·ActionChains 폴백 / Playwright 공용).
- 스캔 결과의 전체 XPath를 잘림 없이 복사합니다. 개별 `사용`은 편집기 입력과 동시에 클립보드에 복사하고, `스캔 XPath 모두 복사`로 전체 목록을 한 번에 복사합니다.
- 스캔 XPath 생성식이 `data-testid`·`placeholder`·`aria-label`·`type`·`class`까지 활용해 바로 쓸 수 있는 구체적인 XPath를 만듭니다.
- **DOM 분석 번들(.zip)** 저장을 추가했습니다. 보고서 HTM + manifest.json + 문서별 원본 HTML을 묶어 추후 재분석에 활용할 수 있습니다 (Selenium/Playwright 공용).

### 수정
- 자동 탐색 스캔 JS의 따옴표 토큰 오류로 모든 프레임 스캔이 V8 SyntaxError로 실패하던 문제를 고쳤습니다. 내비게이션 중인 프레임 하나가 전체 스캔을 죽이지 않도록 프레임 단위로 격리했습니다.
- 요소 선택기(picker) 주입 스크립트의 따옴표 토큰·CSS 이스케이프 오류로 주입이 조용히 실패하던 문제를 고쳤습니다.
- Selenium 클릭 경로를 추가하고 요소 탐색 실패 시 짧게 재시도하도록 했습니다.

## v4.3 - 2026-08-21

기능 감사(`PROJECT_AUDIT.md`)에서 확인한 사용자 기능·보안·안정성 이슈를 반영한 릴리즈입니다.

### 사용자 기능
- 오버레이 모드가 실제로 동작합니다. 기본값은 켜짐이며, 끄면 페이지 클릭이 전달됩니다.
- 종료/설정 열기/새 설정/프리셋 전환 시 저장하지 않은 XPath 목록을 확인합니다.
- Playwright로 스캔한 항목은 Playwright 세션이 살아 있으면 그 엔진으로 검증·하이라이트·미리보기합니다.
- Undo/Redo 한도를 문서와 UI에 최대 50단계로 명시합니다.

### 보안
- AI API 키는 `ai_config.json`에 저장하지 않습니다. 환경변수가 파일에 남은 키보다 우선합니다.
- 쿠키 저장 전 경고, 현재 페이지 도메인과 맞는 쿠키만 주입, `sameSite` 호환 처리, 원자적 쓰기.
- Picker 툴팁 HTML 이스케이프, CSV 수식 주입 방지, `javascript:`/`data:` URL 거부.

### 안정성
- 라이브 미리보기 워커가 이전 작업을 기다린 뒤 다시 시작합니다.
- 피커/검증/배치/시나리오가 같은 브라우저 드라이버를 동시에 쓰지 않습니다.
- 시나리오 wait/popup 대기 상한 60초.
- 설정 파일 `items`가 리스트가 아니면 로드를 실패시킵니다.
- QSettings 식별자를 `XPathExplorer`로 통일하고, 구 `MyCompany` 값을 한 번 이관합니다.

### 개발
- `xpath_explorer/browser/engine_router.py`, `tools/csv_safety.py`, `core/url_safety.py`, `core/cookie_safety.py`, `core/config_state.py`, `workers/driver_guard.py` 추가.
- 관련 단위 테스트와 문서 동기화 점검 보강.
