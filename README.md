# 🔍 XPath Explorer v4.2

> **티켓 사이트 및 복잡한 웹 애플리케이션 자동화를 위한 강력한 데스크톱 XPath 탐색·분석·검증·관리 도구**

XPath Explorer는 인터파크, 멜론티켓, YES24 등 복잡한 티켓팅 사이트와 동적 웹사이트의 요소를 직관적으로 추출하고, 다중 팝업 및 iframe 환경에서도 안정적으로 검증하며, 자동화 코드까지 원클릭으로 생성해 주는 PyQt6 기반 데스크톱 애플리케이션입니다.

---

## 📑 목차
- [✨ 핵심 기능](#-핵심-기능)
- [📦 설치 및 환경 설정](#-설치-및-환경-설정)
- [🚀 빠른 실행](#-빠른-실행)
- [📖 상세 사용 가이드](#-상세-사용-가이드)
  - [1. 브라우저 연결 및 사이트 탐색](#1-브라우저-연결-및-사이트-탐색)
  - [2. XPath 요소 수집 (3가지 방법)](#2-xpath-요소-수집-3가지-방법)
  - [3. 선택자 검증 및 최적화](#3-선택자-검증-및-최적화)
  - [4. 일괄 검증(배치) 및 시나리오 자동화](#4-일괄-검증배치-및-시나리오-자동화)
  - [5. 자동화 코드 생성 및 내보내기](#5-자동화-코드-생성-및-내보내기)
- [🧰 고급 생산성 도구](#-고급-생산성-도구)
- [⌨️ 단축키 안내](#️-단축키-안내)
- [📁 프로젝트 아키텍처](#-프로젝트-아키텍처)
- [🔨 빌드 및 배포](#-빌드-및-배포)
- [🧪 개발 및 품질 검증](#-개발-및-품질-검증)
- [📄 라이선스](#-라이선스)

---

## ✨ 핵심 기능

- 🎯 **대화형 시각적 요소 선택기 (Visual Element Picker)**: 브라우저 상에서 마우스 호버/클릭으로 요소를 즉각 선택하고 견고한 XPath를 자동 추출합니다. 실수 클릭을 방지하는 **오버레이 모드**와 **요소 고정(Lock)** 기능을 제공합니다.
- 🤖 **AI XPath 어시스턴트**: OpenAI(`gpt-5.4`) 및 Google Gemini(`gemini-flash-latest`)와 연동하여 자연어 설명("로그인 버튼", "날짜 선택 셀")만으로 최적의 XPath를 생성합니다.
- 🪟 **다중 창/팝업 & 중첩 iframe 완벽 지원**: 예매 팝업창, 본인인증 팝업 및 인터파크 좌석 예매 iframe(`ifrmSeat` 등)의 문맥을 자동 기억하여 정확한 위치에서 검증 및 하이라이트를 수행합니다.
- 🔍 **Playwright 자동 페이지 스캔**: 버튼, 입력 필드, 링크 등 페이지 내 상호작용 가능한 모든 요소를 일괄 스캔하여 목록화합니다.
- 💡 **XPath 자동 최적화 (Optimizer)**: ID, `data-*`, name, class, 텍스트, 부모-자식 관계 등 가중치 기반으로 안정성이 높은 다중 대안 XPath를 추천합니다.
- 📊 **배치 테스트 & 시나리오 실행기**: 등록된 XPath의 일괄 동작 테스트, 성공률 집계 및 팝업/대기 액션이 포함된 시나리오 자동 실행을 지원합니다.
- 🧾 **DOM 스냅샷 및 DOM Diff 분석**: 전체 페이지/iframe의 DOM을 단일 `.htm`으로 저장하고, 변경 전후의 구조 차이를 시각적으로 비교하는 리포트를 생성합니다.
- 🔧 **매크로 및 자동화 코드 생성**: Python Selenium, Playwright Python, PyAutoGUI 실행 코드를 원클릭으로 생성하고 내보냅니다.
- 🔄 **안전한 상태 관리**: 무제한 Undo/Redo(Ctrl+Z / Ctrl+Y) 및 원자적 파일 저장(`atomic_write_json`)으로 작업 손실을 완벽 방지합니다.

---

## 📦 설치 및 환경 설정

### 1. 가상환경 생성 및 의존성 설치

```bash
# 가상환경 생성 (Python 3.10+ 권장)
python -m venv .venv

# 가상환경 활성화 (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# pip 최신화
python -m pip install --upgrade pip

# 개발 및 전체 기능용 의존성 설치 (권장)
python -m pip install -r requirements/requirements-dev.txt

# 또는 기본 패키지만 설치
# python -m pip install -r requirements/requirements.txt
```

### 2. Playwright Chromium 브라우저 설치 (선택/권장)

네트워크 분석 및 Playwright 자동 스캔 기능을 사용하려면 Chromium을 설치합니다.

```bash
python -m playwright install chromium
```

### 3. AI API 키 설정 (선택)

AI XPath 어시스턴트를 사용하려면 메뉴의 `도구(T) > 🤖 AI XPath 추천...` 다이얼로그에서 설정하거나 환경변수를 등록합니다.
- OpenAI: `OPENAI_API_KEY`
- Google Gemini: `GEMINI_API_KEY` (또는 `GOOGLE_API_KEY`)

---

## 🚀 빠른 실행

```bash
# 1. 패키지 모듈 진입점 (권장)
python -m xpath_explorer

# 2. 레거시 호환 진입점 실행
python "xpath 조사기(모든 티켓 사이트).py"
```

---

## 📖 상세 사용 가이드

### 1. 브라우저 연결 및 사이트 탐색

```
[ 상단 브라우저 컨트롤 패널 ]
[🌐 브라우저 열기] ── [사이트 프리셋 선택: 인터파크 ▼] ── [URL 입력창] ── [창 / 프레임 선택]
```

1. 프로그램 상단의 **`🌐 브라우저 열기`** 버튼을 클릭하여 제어용 Chrome 브라우저를 실행합니다.
2. **사이트 프리셋** 드롭다운에서 대상 사이트를 선택하거나 URL을 직접 입력한 뒤 `이동`을 누릅니다.
   - **기본 프리셋**: 인터파크(NOL/야놀자 통합), 멜론티켓, YES24 등 사전 정의된 요소 세트 탑재
3. **창 / 프레임 자동 감지**:
   - 팝업 예매창이 열리면 `창` 드롭다운에서 해당 창을 선택하거나 `↻` 버튼으로 목록을 갱신합니다.
   - 인터파크 좌석선택창 등 iframe 내부 요소를 다룰 때는 `프레임` 드롭다운 또는 `🔍` 버튼을 눌러 대상 iframe을 선택합니다.

---

### 2. XPath 요소 수집 (3가지 방법)

#### 방법 A. 🎯 대화형 시각적 요소 선택기 (Visual Picker)
1. 오른쪽 패널 **`📝 편집기`** 탭에서 **`🎯 요소 선택 시작`** 버튼을 클릭합니다.
2. 브라우저 화면에서 마우스를 가져가면 요소가 하이라이트됩니다.
3. **`오버레이 모드 (클릭 방지)`** 체크 시 버튼 클릭 액션이 실행되지 않고 안전하게 요소 선택만 진행됩니다.
4. 원하는 요소 위에서 클릭하거나, **`📌 현재 요소 고정`** 버튼을 누르면 해당 요소의 XPath, 태그, 텍스트 및 기본 속성이 편집기에 자동으로 입력됩니다.

#### 방법 B. 🔍 Playwright 자동 일괄 스캔 (Auto Scan)
1. 오른쪽 패널 **`🔍 자동 탐색`** 탭으로 이동합니다.
2. **`▶ Playwright 시작`**을 클릭하여 탐색 브라우저를 활성화합니다.
3. 스캔 타입(버튼, 입력 필드, 링크, 폼, 상호작용 요소 전체) 및 스캔 범위(현재 프레임, 현재 창 전체, 모든 팝업)를 선택합니다.
4. **`🔍 페이지 스캔`** 버튼을 누르면 페이지 내 모든 대상 요소를 찾아 표로 정리해 줍니다.
5. 표에서 원하는 항목의 `사용`을 클릭하면 즉시 편집기 및 목록으로 불러옵니다.

#### 방법 C. 🤖 AI XPath 추천 어시스턴트
1. 상단 메뉴 `도구(T) > 🤖 AI XPath 추천...`을 실행합니다.
2. 찾고자 하는 요소를 자연어로 입력합니다. (예: *"좌석 등급 VIP 선택 버튼"*, *"로그인 폼의 아이디 입력창"*)
3. **`🔮 XPath 생성`**을 누르면 AI가 최적의 XPath, 대안 목록, 신뢰도 및 상세 설명을 생성합니다.
4. **`적용`**을 눌러 편집기로 바로 가져옵니다.

---

### 3. 선택자 검증 및 최적화

1. **실시간 매칭 피드백**:
   - 편집기의 XPath 입력창에 수식을 입력하면 상단에 `🔍 매칭: 1개`와 같이 실시간으로 일치하는 요소 개수를 알려줍니다.
2. **검증 및 하이라이트**:
   - **`검증` (단축키: `Ctrl+T`)**: 브라우저에서 실제 요소를 찾아 태그, 텍스트, 크기, 위치, 속성을 표시합니다.
   - **`하이라이트`**: 브라우저 화면에서 해당 요소의 테두리를 강조 표시합니다.
3. **💡 XPath 대안 추천 (Optimizer)**:
   - XPath 입력창 우측의 **`💡`** 버튼을 클릭합니다.
   - ID 기반, `data-*` 속성 기반, name, class 조합, 텍스트 일치(`normalize-space`), 부모-자식 관계 등 견고성 점수(Robustness Score) 순으로 정렬된 여러 XPath 대안 중 가장 안정적인 수식을 선택할 수 있습니다.
4. **목록 저장**:
   - 이름, 카테고리(login, booking, seat, captcha 등), 설명, 태그를 입력한 후 **`목록에 저장`**을 클릭합니다.

---

### 4. 일괄 검증(배치) 및 시나리오 자동화

1. **전체 검증 (`F5`)**:
   - 현재 등록된 모든 XPath 항목을 순차적으로 검증하여 유효성을 판별하고 성공률 통계를 갱신합니다.
2. **카테고리별 배치 테스트**:
   - 메뉴 `도구(T) > 📊 배치 테스트`에서 특정 카테고리(예: `seat`만 선택)를 지정하여 일괄 검증합니다.
3. **시나리오 실행기 (Scenario Runner)**:
   - 메뉴 `도구(T) > 📊 배치 테스트 > 시나리오 실행기...`를 실행합니다.
   - 팝업 대기(`wait_for_popup`), 팝업 전환(`switch_latest_popup`), 프레임 전환, 요소 검증이 결합된 JSON 시나리오를 불러와 자동 실행합니다.
4. **리포트 내보내기**:
   - 검증 및 시나리오 결과를 **CSV** 또는 **Markdown** 리포트 파일로 즉시 저장할 수 있습니다.

---

### 5. 자동화 코드 생성 및 내보내기

1. **내보내기 메뉴 (`파일(F) > 내보내기(E)`)**:
   - **JSON 파일 (`.json`)**: 전체 설정 및 XPath 목록 백업
   - **CSV 파일 (`.csv`)**: 스프레드시트 분석용
   - **파이썬 Selenium (`.py`)**: Selenium WebDriver용 자동화 스크립트 코드
   - **자바스크립트 (`.js`)**: 브라우저 콘솔 및 Puppeteer/Node.js 호환 코드
2. **매크로 생성기 (`도구(T) > 🔧 매크로 생성...`)**:
   - 등록된 XPath들을 조합하여 Selenium Python, Playwright Python, PyAutoGUI 기반의 매크로/테스트 코드를 자동 생성합니다.

---

## 🧰 고급 생산성 도구

| 도구 | 메뉴 위치 | 설명 |
|------|-----------|------|
| **XPath 템플릿 라이브러리** | `도구 > 📚 XPath 템플릿 라이브러리...` | 버튼, 폼, 테이블, 텍스트 매칭 등 자주 쓰는 검증된 XPath 패턴 검색 및 즉시 적용 |
| **DOM 비교 (Diff) 리포트** | `도구 > 🧾 DOM 비교 리포트` | 기준 페이지 대비 DOM 변경점을 분석하여 차이점을 시각적 HTML 리포트로 출력 |
| **DOM 추출 (.htm)** | 편집기 / 자동 탐색 패널 | 전체 페이지, 현재 창, iframe을 포함한 원본 DOM을 단일 `.htm` 파일로 저장 |
| **쿠키 관리** | `도구 > 쿠키 관리` | 로그인 세션 쿠키를 로컬에 저장하고 필요 시 다시 불러와 로그인 상태 유지 |
| **요소 스크린샷** | `도구 > 📸 요소 스크린샷...` | 선택된 XPath 요소 영역만 정밀 캡처하여 이미지로 저장 |
| **검증 히스토리 & 통계** | `도구 > 🕒 검증 히스토리 / 📈 통계` | 최근 검증 이력 500건 조회, 요소별 누적 성공률 및 응답 시간 분석 |
| **오류 텔레메트리 & 진단** | `도구 > 🚨 오류 텔레메트리 / 🧭 기능 진단` | 브라우저 세션 상태, 프레임 구조, 런타임 에러 집계 및 Markdown 진단 리포트 출력 |

---

## ⌨️ 단축키 안내

| 단축키 | 기능 |
|--------|------|
| <kbd>Ctrl</kbd> + <kbd>N</kbd> | 새 XPath 항목 추가 / 새 설정 |
| <kbd>Ctrl</kbd> + <kbd>O</kbd> | 설정 파일 열기 |
| <kbd>Ctrl</kbd> + <kbd>S</kbd> | 현재 설정 저장 |
| <kbd>Ctrl</kbd> + <kbd>T</kbd> | 현재 입력된 XPath 즉시 테스트(검증) |
| <kbd>F5</kbd> | 등록된 전체 XPath 유효성 검증 |
| <kbd>Ctrl</kbd> + <kbd>Z</kbd> | 실행 취소 (Undo) |
| <kbd>Ctrl</kbd> + <kbd>Y</kbd> | 다시 실행 (Redo) |
| <kbd>Ctrl</kbd> + <kbd>H</kbd> | XPath 수정 히스토리 조회 |
| <kbd>Ctrl</kbd> + <kbd>+</kbd> / <kbd>-</kbd> / <kbd>0</kbd> | UI 폰트 크기 확대 / 축소 / 초기화 |
| <kbd>Delete</kbd> | 목록에서 선택된 항목 삭제 |

---

## 📁 프로젝트 아키텍처

이 프로젝트는 유지보수성과 확장성을 위해 모듈화된 계층형 패키지 구조를 채택하고 있습니다.

### 핵심 모듈 및 패키지 구조

| 경로 | 설명 |
|------|------|
| `xpath_explorer/main_window.py` | 메인 윈도우 공개 호환 facade |
| `xpath_explorer/app/main_window.py` | 실제 애플리케이션 조립, Qt bootstrap 및 `XPathExplorer` 구현체 |
| `xpath_explorer/ai/` | OpenAI / Gemini API 연동 어시스턴트 및 프롬프트/모델 내부 구현 |
| `xpath_explorer/browser/` | Selenium 및 Playwright 브라우저 제어 매니저 facade 및 DOM 추출 모듈 |
| `xpath_explorer/core/browser_assets/` | 브라우저 주입용 요소 선택기(Picker) JavaScript 스크립트 및 에셋 |
| `xpath_explorer/mixins/ui_mixin.py` | 메뉴, 패널, 레이아웃 조립 Mixin facade |
| `xpath_explorer/mixins/browser_mixin.py` | 네비게이션, 프레임, 브라우저 제어 Mixin facade |
| `xpath_explorer/mixins/data_mixin.py` | 파일 입출력, 설정, 필터링, 히스토리 Mixin facade |
| `xpath_explorer/mixins/tools_mixin.py` | 배치 실행, 시나리오, 진단, 리포트 도구 Mixin facade |
| `xpath_explorer/ui/` | 고성능 Model/View 테이블 모델 및 필터 프록시 |
| `xpath_explorer/ui/components/` | 커스텀 UI 위젯, 휠 방지 콤보박스 및 입력 컴포넌트 |
| `xpath_explorer/workers/background.py` | 백그라운드 비동기 검증, 스캔, AI 작업 처리 QThread 워커 facade |
| `packaging/pyinstaller/xpath_explorer.spec` | PyInstaller 단일 실행 파일(`.exe`) 배포 빌드 스펙 |

---

## 🔨 빌드 및 배포

PyInstaller를 사용하여 단일 실행 파일(`.exe`)을 빌드할 수 있습니다.

```bash
# 전체 기능 의존성 설치 후 빌드 (권장)
python -m pip install -r requirements/requirements-full.txt

# PyInstaller 빌드 실행
pyinstaller packaging/pyinstaller/xpath_explorer.spec
```

- **빌드 결과물**: `dist/XPathExplorer_v4.2.exe` (약 50~80MB)
- **특징**: UPX 압축 지원, Chromium 드라이버 및 필수 에셋 번들링, headless-safe Qt 부트스트랩 지원

---

## 🧪 개발 및 품질 검증

프로젝트의 안정성과 문서 정합성을 위해 자동화된 품질 검증 스크립트를 제공합니다.

```bash
# 1. 문서-코드 동기화 및 필수 토큰 검사
python scripts/check_docs_sync.py --strict-warnings

# 2. UTF-8 인코딩 및 모지바케 검사
python scripts/check_encoding_health.py

# 3. 정적 타입 검사 (Pyright)
python -m pyright -p .

# 4. 단위 테스트 실행
pytest -q

# 5. 종합 품질 및 릴리즈 스모크 체크
python scripts/run_quality_checks.py --strict-doc-warnings --smoke-release
```

---

## 📄 라이선스

This project is licensed under the **MIT License**.
