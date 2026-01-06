# 🔍 XPath Explorer v4.1

티켓 사이트 및 웹 자동화를 위한 강력한 XPath 요소 탐색, 분석, 관리 도구

## ✨ v4.1 업데이트 (2026.01)

### 🐛 버그 수정
- AI 설정 초기화 오류 수정
- 사이트 조사 시 프레임 복구 누락 수정
- 요소 선택기 스레드 정리 개선
- 하이라이트 시 브라우저 연결 체크 추가

### 🎨 UI/UX 개선
- 연결 상태 glow 애니메이션
- 테이블 선택/hover 효과 강화
- 검색창 초기화(X) 버튼
- 빈 상태 안내 메시지

---

## 🤖 AI XPath 어시스턴트
- **OpenAI & Gemini 연동**: 자연어로 XPath 자동 생성
- **멀티 모델 지원**: GPT-4o, Gemini Flash 등

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
# 필수
pip install PyQt6 selenium undetected-chromedriver webdriver-manager

# AI (선택)
pip install openai google-generativeai

# Playwright (선택)
pip install playwright && playwright install chromium
```

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

빌드 결과: `dist/XPathExplorer_v4.1.exe` (약 50-80MB)

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
