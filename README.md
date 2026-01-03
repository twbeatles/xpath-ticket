# 🔍 XPath Explorer v3.5

티켓 사이트 XPath 요소 탐색 및 관리 도구

## ✨ 주요 기능

### 브라우저 자동화
- **Selenium + Undetected ChromeDriver**: 자동화 탐지 우회
- **Playwright 지원**: 고급 요소 자동 스캔
- **중첩 iframe 지원**: 인터파크 등 복잡한 구조 탐색

### XPath 관리
- 📋 항목 저장/편집/삭제
- 🔍 실시간 검색 (Debounce 적용)
- ⭐ 즐겨찾기 및 태그 분류
- 📊 배치 테스트 및 성공률 통계
- 🔄 드래그 앤 드롭 정렬

### 코드 생성
- Python Selenium 스크립트
- Python Playwright 스크립트
- PyAutoGUI 스크립트

### 내보내기
- JSON, Python Dict, CSV, Markdown

---

## 📦 설치

### 필수 요구사항
- Python 3.10+
- Chrome 브라우저

### 의존성 설치
```bash
pip install PyQt6 selenium undetected-chromedriver webdriver-manager
pip install playwright  # 선택사항
playwright install chromium  # Playwright 사용 시
```

---

## 🚀 실행

```bash
python "xpath 조사기(모든 티켓 사이트).py"
```

---

## 🔨 빌드 (PyInstaller)

```bash
pyinstaller xpath_explorer.spec
```

빌드 결과: `dist/XPathExplorer_v3.5.exe`

---

## 📁 프로젝트 구조

```
xpath/
├── xpath 조사기(모든 티켓 사이트).py  # 메인 앱
├── xpath_browser.py        # Selenium 브라우저 관리
├── xpath_playwright.py     # Playwright 지원
├── xpath_codegen.py        # 코드 생성기
├── xpath_config.py         # 설정 및 데이터 클래스
├── xpath_constants.py      # 상수 및 프리셋
├── xpath_statistics.py     # 통계 관리
├── xpath_styles.py         # 스타일시트
├── xpath_widgets.py        # 커스텀 위젯
├── xpath_workers.py        # 백그라운드 작업
└── xpath_explorer.spec     # PyInstaller 빌드
```

---

## ⌨️ 단축키

| 단축키 | 기능 |
|--------|------|
| Ctrl+N | 새 항목 |
| Ctrl+S | 저장 |
| Ctrl+T | XPath 테스트 |
| Ctrl+O | 파일 열기 |
| Delete | 항목 삭제 |

---

## 📌 지원 사이트 프리셋

- 인터파크 티켓
- 멜론티켓
- YES24 티켓
- 티켓링크
- 네이버 예약

---

## 📄 라이선스

MIT License
