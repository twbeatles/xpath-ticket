# Changelog

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
