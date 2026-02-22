# 🔍 XPath Explorer v4.2

티켓 사이트 및 웹 자동화를 위한 강력한 XPath 요소 탐색, 분석, 관리 도구

## ✨ v4.2 업데이트 (2026.01)

### 🛡️ 보안 및 안정성 강화
- **핵심 수정**: LocalStorage XSS 취약점 해결, 네트워크 리스너 메모리 누수 수정
- **스레드 안정성**: 요소 선택 감시자(PickerWatcher) 스레드 동기화 개선
- **메모리 최적화**: 히스토리 관리 메모리 사용량 최적화
- **견고성 강화**: 프레임 캐시 무효화 로직으로 네비게이션 안정성 확보

### ⚡ 기능 개선
- **프레임 지원**: 프레임 전환(`switch_to_frame`) 기능 구현 완료
- **CSS/XPath**: 특수 문자(따옴표, ID 등) 이스케이프 처리 강화
- **검증 경로**: PDF 저장 시 Headless 모드 검증 로직 추가

### 🧰 안정화 패치 (2026.02)
- **Code Generator Fix**: Selenium/Playwright/PyAutoGUI 코드 생성 시 문자열 포맷 충돌(`KeyError`) 수정
- **Network Analyzer Recovery**: `NetworkAnalyzer` 어댑터 복구 및 응답 크기(`response_size`) 표시 지원
- **History Integrity**: preset/new/open 직후 Undo 기준점 재설정으로 히스토리 오염 방지
- **Validation Data Flow**: 단일/전체/배치 검증 결과를 통합 기록(통계 + Diff 스냅샷)

### 🎨 UI/UX 개선 (v4.1)
- 연결 상태 glow 애니메이션
- 테이블 선택/hover 효과 강화
- 검색창 초기화(X) 버튼
- 빈 상태 안내 메시지

---

## 🤖 AI XPath 어시스턴트
- **OpenAI & Gemini 연동**: 자연어로 XPath 자동 생성
- **멀티 모델 지원**: GPT-5.2, Gemini Flash Latest 등 최신 경량 모델

## 🔄 히스토리 & 안전 장치
- **Undo/Redo**: 무제한 히스토리
- **Diff 분석**: 페이지 변경 감지

## ⚡ 생산성 도구
- 실시간 미리보기
- XPath 최적화
- 요소 스크린샷

---

## 📦 설치

```bash
# (권장) requirements 사용
pip install -r requirements-full.txt

# 최소 설치만 원하면
# pip install -r requirements.txt

# Playwright Chromium 설치 (선택 기능이지만 EXE에서도 동일 기능 사용 시 필요)
python -m playwright install chromium
```

> 네트워크 분석/Playwright 스캔 기능은 Chromium 설치가 되어 있어야 정상 동작합니다.

---

## 🚀 실행

```bash
python "xpath 조사기(모든 티켓 사이트).py"
```

---

## 🔨 빌드 (PyInstaller)

```bash
# UPX 설치 시 경량화 적용 (권장)
    pyinstaller xpath_explorer.spec
    ```

    빌드 결과: `dist/XPathExplorer_v4.2.exe` (약 50-80MB)

---

## 📁 프로젝트 구조

| 파일 | 설명 |
|------|------|
| `xpath 조사기(모든 티켓 사이트).py` | 메인 애플리케이션 |
| `xpath_ai.py` | AI 어시스턴트 |
| `xpath_browser.py` | 브라우저 제어 (Selenium) |
| `xpath_playwright.py` | Playwright 통합 |
| `xpath_optimizer.py` | XPath 최적화 |
| `xpath_history.py` | Undo/Redo |
| `xpath_diff.py` | 변경사항 분석 |
| `xpath_codegen.py` | 코드 생성기 |
| `xpath_statistics.py` | 테스트 통계 |
| `xpath_styles.py` | UI 스타일 |

---

## ⌨️ 단축키

| 단축키 | 기능 |
|--------|------|
| Ctrl+N | 새 항목 |
| Ctrl+S | 저장 |
| Ctrl+Z | 실행 취소 |
| Ctrl+Y | 다시 실행 |
| Ctrl+T | XPath 테스트 |
| Delete | 삭제 |

---

## 📄 라이선스

MIT License

---

## 성능 아키텍처 (v4.2 리팩터링)

- `QTableWidget` 기반 목록 렌더링을 `QTableView + XPathItemTableModel + XPathFilterProxyModel` 구조로 교체했습니다.
- 검색/카테고리/태그/즐겨찾기 필터는 전체 행 재렌더링 대신 프록시 무효화 기반으로 동작합니다.
- Selenium 검증 경로는 재사용 가능한 검증 세션을 지원합니다.
  - `begin_validation_session()`
  - `validate_xpath(xpath, preferred_frame=None, session=None)`
  - `end_validation_session(session)`
- `get_element_info()`는 다음 옵션을 지원합니다.
  - `include_attributes=True|False`
  - `session` 캐시 재사용
- 통계 저장은 비동기 배치 방식으로 동작합니다.
  - `record_test()`는 메모리 상태만 갱신
  - 백그라운드 writer가 주기적으로 flush 수행
  - `save()`는 동기 flush 동작 유지
  - `shutdown(timeout=...)`은 종료 시 flush 후 writer thread 정지
- 성능 지표는 `perf_span`으로 집계되며 앱 종료 시 요약(`count/avg/p95/max`)을 출력합니다.

## 모듈 구조 (v4.2 분할)

- 하위 호환을 위해 레거시 진입점 파일을 유지합니다.
  - `xpath 조사기(모든 티켓 사이트).py`는 새 앱 패키지를 import 후 실행합니다.
- 메인 윈도우 조합 로직:
  - `xpath_explorer/main_window.py`
- 런타임 로거 초기화:
  - `xpath_explorer/runtime.py`
- 기존 단일 클래스 `XPathExplorer` 메서드는 책임별로 분리되었습니다.
  - `xpath_explorer/mixins/ui_mixin.py`
  - `xpath_explorer/mixins/browser_mixin.py`
  - `xpath_explorer/mixins/data_mixin.py`
  - `xpath_explorer/mixins/tools_mixin.py`

호환 정책:
- 기존 실행 명령은 변경하지 않습니다.
- 기존 JSON 스키마와 사용자 UI 라벨 호환성을 유지합니다.
