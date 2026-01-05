# 🔍 XPath Explorer v4.0

티켓 사이트 및 웹 자동화를 위한 강력한 XPath 요소 탐색, 분석, 관리 도구

## ✨ v4.0 주요 신규 기능

### 🤖 AI XPath 어시스턴트
- **OpenAI & Gemini 연동**: 자연어 설명만으로 최적의 XPath 자동 생성
- **멀티 모델 지원**: GPT-4o, Gemini Flash 등 선택 가능
- **스마트 추천**: 요소의 특징을 분석하여 신뢰도 높은 선택자 제안

### 🔄 히스토리 & 안전 장치
- **Undo/Redo**: 실수로 삭제하거나 수정한 항목을 즉시 복구 (무제한 히스토리)
- **Diff 분석**: 페이지 변경 사항을 감지하여 기존 XPath가 유효한지 검증

### ⚡ 생산성 도구
- **실시간 미리보기**: 입력한 XPath가 현재 페이지에서 몇 개의 요소를 찾는지 즉시 확인
- **XPath 최적화**: 불안정한 XPath를 ID, Class, 계층 구조 기반의 견고한 형태로 자동 변환
- **요소 스크린샷**: 선택한 영역을 즉시 캡처하여 저장

---

## 🛠️ 핵심 기능

### 브라우저 자동화
- **Selenium + Undetected ChromeDriver**: 자동화 탐지 우회
- **Playwright 지원**: 빠르고 강력한 최신 브라우저 자동화
- **중첩 iframe 완벽 지원**: 인터파크 등 복잡한 프레임 구조 자동 탐색

### 관리 및 테스트
- 📋 항목 그룹화 및 태그 관리
- 📊 대량 배치 테스트 및 성공률 통계
- 🔍 실시간 검색 및 필터링
- 💾 JSON, CSV, Python 코드 내보내기

---

## 📦 설치

### 필수 요구사항
- Python 3.10+
- Chrome 브라우저

### 의존성 설치
```bash
# 기본 의존성
pip install PyQt6 selenium undetected-chromedriver webdriver-manager

# AI 기능 (선택사항)
pip install openai google-generativeai

# Playwright (선택사항 - 고급 기능)
pip install playwright
playwright install chromium
```

---

## 🚀 실행

```bash
python "xpath 조사기(모든 티켓 사이트).py"
```

---

## 🔨 빌드 (PyInstaller)

단독 실행 파일(.exe) 생성:

```bash
pyinstaller xpath_explorer.spec
```

빌드 결과물은 `dist/XPathExplorer_v4.0.exe`에 생성됩니다.

---

## 📁 프로젝트 구조

```
xpath/
├── xpath 조사기(모든 티켓 사이트).py  # 메인 애플리케이션
├── xpath_ai.py             # AI 어시스턴트 (OpenAI/Gemini)
├── xpath_browser.py        # 브라우저 제어 (Selenium)
├── xpath_playwright.py     # Playwright 통합
├── xpath_optimizer.py      # XPath 최적화 로직
├── xpath_history.py        # Undo/Redo 관리
├── xpath_diff.py           # 변경사항 분석 (Diff)
├── xpath_codegen.py        # 코드 생성기
├── xpath_statistics.py     # 테스트 통계
├── xpath_config.py         # 설정 데이터 구조
├── xpath_constants.py      # 상수 및 프리셋
├── xpath_styles.py         # UI 스타일시트
├── xpath_widgets.py        # 커스텀 위젯UI
└── xpath_explorer.spec     # PyInstaller 빌드 설정
```

---

## ⌨️ 단축키

| 단축키 | 기능 |
|--------|------|
| Ctrl+N | 새 항목 추가 |
| Ctrl+S | 저장 |
| Ctrl+Z | 실행 취소 (Undo) |
| Ctrl+Y | 다시 실행 (Redo) |
| Ctrl+T | XPath 테스트 |
| Delete | 항목 삭제 |

---

## 📄 라이선스

MIT License
