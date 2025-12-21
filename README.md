# 🎯 XPath 탐색기 (XPath Explorer) v3.3

티켓 예매 사이트의 XPath를 탐색하고 관리하는 도구입니다.  
인터파크, 티켓링크, 멜론티켓, YES24 등 다양한 사이트의 요소를 분석할 수 있습니다.

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![PyQt6](https://img.shields.io/badge/PyQt6-GUI-green.svg)
![Selenium](https://img.shields.io/badge/Selenium-WebDriver-orange.svg)
![HiDPI](https://img.shields.io/badge/HiDPI-Supported-purple.svg)

---

## ✨ 주요 기능

### 🔍 요소 선택기
- **클릭 → 고정** 방식으로 원하는 요소 정확하게 선택
- XPath / CSS 선택자 자동 생성
- 클립보드 복사 버튼 제공
- 모든 iframe 내부에서도 작동

### 🖼️ iframe 지원
- 중첩 iframe 최대 5단계까지 재귀 탐색
- 인터파크 좌석선택 팝업 특수 프레임 자동 감지
- 프레임 경로 표시 (예: `ifrmSeat/ifrmSeatDetail`)

### 🪟 다중 윈도우 지원
- 팝업 윈도우 자동 감지
- 탭이 닫혀도 자동으로 다른 윈도우로 복구
- 윈도우 간 쉬운 전환

### 📋 XPath 관리
- 카테고리별 XPath 항목 정리
- 일괄 검증 (F5)
- JSON/YAML/Python 형식으로 내보내기

### 🍪 쿠키/세션 관리 (v3.2)
- 브라우저 쿠키 저장/불러오기
- 로그인 세션 유지

### 📜 XPath 히스토리 (v3.2)
- 선택한 XPath 자동 기록
- 최근 사용 항목 빠른 접근

### 🖼️ HiDPI 지원 (v3.3 NEW)
- 고해상도 디스플레이 자동 스케일링
- DPI 인식 UI 요소
- 4K/Retina 디스플레이 완벽 지원

---

## 🚀 설치

### 요구사항
```
Python 3.8+
PyQt6
selenium
webdriver-manager (선택)
undetected-chromedriver (선택)
```

### 설치 명령어
```bash
pip install PyQt6 selenium webdriver-manager undetected-chromedriver
```

---

## 📖 사용법

### 1. 프로그램 실행
```bash
python "251221 xpath 조사기(모든 티켓 사이트).py"
```

### 2. 브라우저 열기
- **🌐 브라우저 열기** 버튼 클릭
- 사이트 프리셋 선택 (인터파크, 티켓링크 등)
- URL 입력 후 **이동**

### 3. 요소 선택하기
1. **🎯 요소 선택 시작** 버튼 클릭
2. 원하는 요소에 마우스를 올려 확인
3. **클릭** → 선택 고정 🔒
4. **📋 XPath 복사** 또는 **✓ 확인**으로 프로그램에 전송

### 4. iframe 스캔
- 좌석선택 팝업이 열리면 **🔍** 버튼 클릭
- ⭐ 표시가 있는 항목이 좌석 관련 프레임

### 5. 더블클릭 테스트 (v3.2)
- 테이블에서 항목을 **더블클릭**하면 자동으로 XPath 테스트 실행

---

## ⌨️ 키보드 단축키

| 키 | 동작 |
|---|---|
| **F5** | 전체 XPath 검증 |
| **Ctrl+N** | 새 설정 |
| **Ctrl+O** | 설정 열기 |
| **Ctrl+S** | 설정 저장 |
| **Ctrl++** | 폰트 크기 증가 |
| **Ctrl+-** | 폰트 크기 감소 |
| **Ctrl+0** | 폰트 크기 초기화 |
| **Space** | 호버 상태 고정/해제 ⭐ |
| **ESC** | 요소 선택 취소 / 고정 해제 |
| **Enter** | 선택 확정 (고정 상태) |

---

## 📂 사이트 프리셋

| 사이트 | URL |
|---|---|
| 인터파크 | ticket.interpark.com |
| 티켓링크 | ticketlink.co.kr |
| 멜론티켓 | ticket.melon.com |
| 예스24 | ticket.yes24.com |
| 네이버 | booking.naver.com |

---

## 📦 빌드 (EXE 생성)

PyInstaller를 사용하여 실행 파일을 생성할 수 있습니다:

```bash
# PyInstaller 설치
pip install pyinstaller

# EXE 빌드
pyinstaller xpath_explorer.spec
```

빌드된 실행 파일은 `dist/` 폴더에 생성됩니다.

---

## 🔧 디버깅

로그 파일 위치:
```
%USERPROFILE%\.xpath_explorer\debug.log
```

---

## 📋 버전 히스토리

### v3.3 (2025-12)
- **HiDPI 디스플레이 지원**
  - 고해상도 모니터 자동 스케일링
  - DPI 인식 UI 요소 (ToastWidget 등)
  - Qt HighDpiScaleFactorRoundingPolicy 적용
- DPI 스케일링 헬퍼 함수 추가 (`scaled()`, `get_dpi_scale()`)
- 기동 시 DPI 정보 로깅

### v3.2 (2025-12)
- Config 상수 클래스 추가
- 폰트 크기 단축키 구현 (Ctrl++/-/0)
- 테이블 더블클릭 XPath 테스트 기능
- 예외 처리 강화 (bare except 제거)
- closeEvent 타이머/스레드 안전 정리
- 향상된 로깅

### v3.0
- 다중 윈도우/팝업 지원
- XPath 히스토리
- 쿠키/세션 관리
- 오버레이 모드

---

## 📄 라이선스

개인 사용 목적으로 제작되었습니다.

---

## 🙏 기여

버그 리포트나 기능 제안은 이슈로 등록해주세요.
