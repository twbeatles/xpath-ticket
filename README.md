# 🎯 XPath 탐색기 (XPath Explorer) v3.2

티켓 예매 사이트 및 일반 웹사이트의 XPath를 쉽고 정확하게 분석하고 관리하는 전문 도구입니다.  
**인터파크, 티켓링크, 멜론티켓, YES24** 등 주요 예매 사이트에 최적화되어 있으며, 복잡한 iframe이나 팝업 윈도우 환경에서도 강력한 탐색 기능을 제공합니다.

![Python](https://img.shields.io/badge/Python-3.8+-3776AB.svg?style=flat&logo=python&logoColor=white)
![PyQt6](https://img.shields.io/badge/PyQt6-GUI-41CD52.svg?style=flat&logo=qt&logoColor=white)
![Selenium](https://img.shields.io/badge/Selenium-WebDriver-43B02A.svg?style=flat&logo=selenium&logoColor=white)

---

## ✨ v3.2 주요 변경 사항

- **🎨 Modern Dark 테마**: 눈이 편안한 Catppuccin 스타일의 모던 다크 테마 적용
- **🧩 모듈화된 구조**: 유지보수가 용이하도록 코드 분리 (`constants`, `styles`, `config`, `browser`, `widgets` 등)
- **⚡ 성능 최적화**: 검색 Debounce 적용 및 브라우저 통신 효율화
- **🛠️ UI/UX 개선**: 직관적인 버튼 스타일, Toast 알림 개선, 툴팁 강화

---

## 🌟 핵심 기능

### 1. 강력한 요소 선택기 (Picker)
- **Direct Selection**: 브라우저에서 요소를 클릭하여 즉시 XPath 추출
- **Smart Lock**: 클릭하여 선택 상태를 고정하고 세부 정보 확인
- **Overlay Mode**: 웹페이지의 클릭 이벤트를 차단하고 선택에만 집중하는 모드 지원
- **Auto-Generate**: 최적화된 XPath 및 CSS Selector 자동 생성

### 2. 지능형 프레임/윈도우 탐색
- **Deep Scan**: 중첩된 iframe (최대 5단계) 재귀적 탐색
- **Auto Detect**: 팝업 윈도우 및 동적 생성 프레임 자동 감지
- **Context Aware**: 선택된 요소가 어느 프레임에 있는지 경로 추적 (`main > ifrmSeat > ifrmDetail`)

### 3. 효율적인 관리 및 검증
- **Real-time Validatation**: 현재 페이지에서 즉시 유효성 검증 (`F5` 또는 검증 버튼)
- **History**: 최근 사용한 XPath 기록 자동 저장 (`Ctrl+H`)
- **Presets**: 주요 티켓 사이트별 미리 정의된 필수 요소 목록 제공
- **Export**: JSON, CSV, Python(Selenium), JavaScript 포맷 내보내기

---

## 🚀 설치 및 실행

### 필수 요구사항
- Python 3.8 이상
- Chrome 브라우저

### 설치
```bash
# 필수 패키지 설치
pip install PyQt6 selenium webdriver-manager undetected-chromedriver
```

### 실행
```bash
# 메인 파일 실행
python "251214 xpath 조사기(모든 티켓 사이트).py"
```

### 빌드 (실행 파일 생성)
```bash
# PyInstaller를 사용하여 단일 실행 파일 생성
pyinstaller xpath_explorer.spec
```

---

## 📖 사용 가이드

### 1. 브라우저 연결
1. 상단의 **[브라우저 열기]** 버튼 (파란색)을 클릭합니다.
2. **사이트 프리셋**에서 대상 사이트를 선택하거나 URL을 직접 입력하여 이동합니다.

### 2. 요소 추출
1. **[🎯 요소 선택 시작]** 버튼 (보라색)을 클릭합니다.
2. 브라우저에서 원하는 요소 위에 마우스를 올리면 **붉은색 하이라이트**가 표시됩니다.
3. 요소를 클릭하면 **초록색으로 고정(Lock)** 되며 상세 정보 툴팁이 뜹니다.
4. 툴팁의 **'Use This Element'** 버튼을 누르거나 키보드 `Enter`를 눌러 프로그램으로 가져옵니다.

### 3. 검증 및 저장
1. 편집 패널에서 이름, 설명, 카테고리를 입력합니다.
2. **[검증 (Test)]** 버튼 (주황색)을 눌러 현재 페이지에서 정상적으로 찾아지는지 확인합니다.
3. **[목록에 저장]** 버튼 (초록색)을 눌러 리스트에 추가합니다.

---

## ⌨️ 단축키 목록

| 키 조합 | 동작 |
|---|---|
| **Ctrl + N** | 새 설정 (초기화) |
| **Ctrl + O** | 설정 파일 열기 |
| **Ctrl + S** | 설정 파일 저장 |
| **Ctrl + T** | 현재 입력된 XPath 즉시 테스트 |
| **Ctrl + H** | XPath 히스토리 보기 |
| **F5** | 전체 목록 일괄 유효성 검사 |
| **Ctrl + (+/-)** | 프로그램 폰트 크기 조절 |
| **ESC** | (선택 모드에서) 선택 취소 또는 고정 해제 |

---

## 📂 프로젝트 구조

```
D:\GOOGLE ANTIGRAVITY\XPATH\
│
├── 251214 xpath 조사기....py  # 메인 실행 파일 (Entry Point)
├── xpath_browser.py           # 브라우저 제어 (Selenium)
├── xpath_config.py            # 설정 및 데이터 구조
├── xpath_constants.py         # 상수 및 스크립트 리소스
├── xpath_styles.py            # UI 스타일시트 (Theme)
├── xpath_widgets.py           # 커스텀 위젯 (Toast 등)
├── xpath_workers.py           # 백그라운드 작업 (스레드)
└── xpath_explorer.spec        # PyInstaller 빌드 정보
```

---

## � 문제 해결

**Q. 브라우저가 열리지 않아요.**  
A. 크롬 브라우저 버전에 맞는 드라이버가 필요합니다. `webdriver-manager`가 자동으로 설치하지만, 실패할 경우 수동 업데이트가 필요할 수 있습니다. 이미 실행 중인 크롬 프로세스를 모두 종료하고 다시 시도하세요.

**Q. 요소 선택이 안 돼요.**  
A. 보안이 강력한 사이트(예: 티켓링크)나 특정 iframe 내부에서는 자바스크립트 주입이 차단될 수 있습니다. 이 경우 수동으로 개발자 도구(F12)를 사용하거나, 프로그램의 '프레임 스캔' 기능을 활용하여 해당 프레임으로 전환 후 시도해보세요.

---

## � 라이선스
Personal Use Only.
