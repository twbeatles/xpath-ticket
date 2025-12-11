# 🎯 XPath 탐색기 (XPath Explorer)

티켓 예매 사이트의 XPath를 탐색하고 관리하는 도구입니다. 인터파크, 티켓링크, 멜론티켓 등 다양한 사이트의 요소를 분석할 수 있습니다.

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![PyQt6](https://img.shields.io/badge/PyQt6-GUI-green.svg)
![Selenium](https://img.shields.io/badge/Selenium-WebDriver-orange.svg)

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
python "★ (작동가능)251204 xpath 조사기(모든 티켓 사이트).py"
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

---

## ⌨️ 키보드 단축키

| 키 | 동작 |
|---|---|
| F5 | 전체 XPath 검증 |
| Ctrl+N | 새 설정 |
| Ctrl+O | 설정 열기 |
| Ctrl+S | 설정 저장 |
| ESC | 요소 선택 취소 / 고정 해제 |
| Enter | 선택 확정 (고정 상태) |

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

## 🔧 디버깅

로그 파일 위치:
```
%USERPROFILE%\.xpath_explorer\debug.log
```

---

## 📄 라이선스

개인 사용 목적으로 제작되었습니다.

---

## 🙏 기여

버그 리포트나 기능 제안은 이슈로 등록해주세요.
