# 🔍 XPath Explorer v4.2

티켓 사이트 및 웹 자동화를 위한 강력한 XPath 요소 탐색, 분석, 관리 도구

## ✨ v4.2 업데이트 (2026.01)

### 🛡️ 보안 및 안정성 강화
- **Critical Fixes**: LocalStorage XSS 취약점 해결, 네트워크 리스너 메모리 누수 수정
- **Thread Safety**: 요소 선택 감시자(PickerWatcher) 스레드 동기화 개선
- **Memory Optimization**: 히스토리 관리 메모리 사용량 최적화
- **Robustness**: 프레임 캐시 무효화 로직으로 네비게이션 안정성 확보

### ⚡ 기능 개선
- **Frame Support**: 프레임 전환(`switch_to_frame`) 기능 구현 완료
- **CSS/XPath**: 특수 문자(따옴표, ID 등) 이스케이프 처리 강화
- **Validation**: PDF 저장 시 Headless 모드 검증 로직 추가

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

## Performance Architecture (v4.2 Refactor)

- `QTableWidget` list rendering path was replaced with `QTableView + XPathItemTableModel + XPathFilterProxyModel`.
- Search/category/tag/favorite filters now run through proxy invalidation instead of full row re-render.
- Selenium validation now supports a reusable validation session:
  - `begin_validation_session()`
  - `validate_xpath(xpath, preferred_frame=None, session=None)`
  - `end_validation_session(session)`
- `get_element_info()` now supports:
  - `include_attributes=True|False`
  - `session` cache reuse
- Statistics persistence is now async-batched:
  - `record_test()` updates memory state only
  - background writer performs periodic flush
  - `save()` keeps synchronous flush semantics
  - `shutdown(timeout=...)` flushes and stops writer thread
- Perf metrics are aggregated by `perf_span` and summarized on app shutdown (`count/avg/p95/max`).
