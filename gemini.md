# 🤖 Gemini AI 지침서 - XPath Explorer

> 이 문서는 Google Gemini AI가 XPath Explorer 프로젝트를 이해하고 효과적으로 지원하기 위한 포괄적 가이드입니다.

---

## 📋 프로젝트 개요

**XPath Explorer**는 티켓 사이트(인터파크, 멜론티켓, YES24 등) 웹 자동화를 위한 XPath 요소 탐색, 분석, 관리 도구입니다.

| 항목 | 내용 |
|------|------|
| **버전** | v4.2 |
| **언어** | Python 3.10+ |
| **GUI 프레임워크** | PyQt6 |
| **브라우저 자동화** | Selenium + undetected-chromedriver, Playwright (선택) |
| **AI 통합** | OpenAI API, Google GenAI SDK |
| **테마** | Catppuccin Mocha (다크 테마) |

---

## 🏗️ 프로젝트 구조

```
xpath/
├── xpath 조사기(모든 티켓 사이트).py  # 메인 애플리케이션 (진입점, ~2900줄)
├── xpath_ai.py                       # AI 어시스턴트 (OpenAI/Gemini)
├── xpath_browser.py                  # Selenium 브라우저 제어 (~800줄)
├── xpath_playwright.py               # Playwright 통합
├── xpath_optimizer.py                # XPath 최적화 및 대안 생성
├── xpath_history.py                  # Undo/Redo 히스토리 관리
├── xpath_diff.py                     # 요소 변경사항 분석 (스냅샷 기반)
├── xpath_config.py                   # 설정 및 데이터 클래스
├── xpath_constants.py                # 상수, 프리셋, 스크립트 (~550줄)
├── xpath_codegen.py                  # 코드 생성기 (Python/JS)
├── xpath_statistics.py               # 테스트 통계
├── xpath_styles.py                   # UI 스타일시트 (Catppuccin)
├── xpath_widgets.py                  # 커스텀 PyQt6 위젯 (~730줄)
├── xpath_workers.py                  # 백그라운드 워커 스레드
└── README.md                         # 프로젝트 문서
```

---

## 🔑 핵심 모듈 상세

### 1. **xpath_config.py** - 데이터 모델
```python
@dataclass
class XPathItem:
    """XPath 항목 - 핵심 데이터 구조"""
    name: str                    # 항목 식별자 (예: "login_btn")
    xpath: str                   # XPath 표현식
    category: str                # 카테고리 (login, booking, seat 등)
    css_selector: str            # CSS 선택자
    is_verified: bool            # 검증 여부
    element_tag: str             # 요소 태그명
    element_text: str            # 요소 텍스트
    found_window: str            # 발견된 윈도우
    found_frame: str             # 발견된 프레임 경로
    is_favorite: bool            # 즐겨찾기 여부
    tags: List[str]              # 태그 목록
    test_count: int              # 테스트 횟수
    success_count: int           # 성공 횟수
    last_tested: str             # 마지막 테스트 시간
    sort_order: int              # 정렬 순서
    alternatives: List[str]      # 대안 XPath 목록
    element_attributes: Dict     # 저장된 요소 속성
    screenshot_path: str         # 스크린샷 경로
    ai_generated: bool           # AI 생성 여부
    
    @property
    def success_rate(self) -> float:
        """성공률 계산 (0-100%)"""
        
    def record_test(self, success: bool):
        """테스트 결과 기록"""
```

### 2. **xpath_browser.py** - 브라우저 관리
```python
class BrowserManager:
    """Selenium 기반 브라우저 제어"""
    
    # 핵심 메서드
    def create_driver(self, use_undetected: bool = True) -> bool:
        """드라이버 생성 (undetected-chromedriver 지원)"""
    
    def is_alive(self) -> bool:
        """연결 상태 확인 (자동 복구 포함)"""
    
    def get_all_frames(self, max_depth: int = 5) -> List[tuple]:
        """모든 iframe 재귀 탐색 (중첩 프레임 지원)"""
    
    def switch_to_frame_by_path(self, frame_path: str) -> bool:
        """프레임 경로로 전환 (예: 'ifrmSeat/ifrmSeatDetail')"""
    
    def find_element_in_all_frames(self, xpath: str) -> Tuple[Optional[Any], str]:
        """모든 프레임에서 요소 검색"""
    
    def validate_xpath(self, xpath: str) -> Dict:
        """XPath 검증 (중첩 iframe 지원)"""
    
    def get_element_info(self, xpath: str) -> Optional[Dict]:
        """요소 상세 정보 (Diff 분석용)"""
    
    def screenshot_element(self, xpath: str, save_path: str) -> bool:
        """요소 스크린샷 저장"""
```

### 3. **xpath_optimizer.py** - XPath 최적화
```python
class XPathOptimizer:
    """XPath 자동 최적화 및 대안 생성기"""
    
    # 안정성 점수 가중치
    strategy_weights = {
        "id": 95,         # ID 기반 - 가장 안정적
        "data-attr": 90,  # data-* 속성
        "name": 85,       # name 속성
        "class": 70,      # class 기반
        "text": 65,       # 텍스트 기반
        "ancestor": 60,   # 부모-자식 관계
        "relative": 50,   # 상대 경로
        "attributes": 45, # 기타 속성 조합
        "index": 30,      # 인덱스 기반 - 가장 취약
    }
    
    def generate_alternatives(self, element_info: Dict) -> List[XPathAlternative]:
        """요소 정보로부터 여러 XPath 대안 생성"""
        
    def calculate_robustness(self, xpath: str) -> int:
        """XPath 안정성 점수 계산 (0-100)"""
        
    def _escape_xpath_text(self, text: str) -> str:
        """XPath 문자열 따옴표 이스케이프 (concat 함수 사용)"""
```

### 4. **xpath_history.py** - 히스토리 관리
```python
class HistoryManager:
    """Undo/Redo 히스토리 관리자 (스레드 안전)"""
    
    def __init__(self, max_history: int = 50):
        self._undo_stack: List[HistoryState] = []
        self._redo_stack: List[HistoryState] = []
        self._lock = RLock()  # 재진입 가능 락
    
    def push_state(self, items, action, item_name, description):
        """현재 상태를 히스토리에 저장 (변경 전 호출)"""
        
    def undo(self) -> Optional[List[Dict]]:
        """실행 취소"""
        
    def redo(self) -> Optional[List[Dict]]:
        """다시 실행"""
```

### 5. **xpath_widgets.py** - 커스텀 위젯
```python
# 휠 스크롤 방지 위젯
class NoWheelComboBox(QComboBox):
    """휠 스크롤로 값이 변경되지 않는 ComboBox"""

# Toast 알림
class ToastWidget(QFrame):
    """모던 Toast 알림 (슬라이드 + 페이드 애니메이션)"""
    THEMES = {"success", "warning", "error", "info"}
    
    def show_toast(self, message, toast_type="info", duration=3000):
        """Toast 메시지 표시"""

# 상태 인디케이터
class AnimatedStatusIndicator(QFrame):
    """펄스 애니메이션이 있는 연결 상태 인디케이터"""
    
    def set_connected(self, connected: bool):
        """연결 상태 설정 (펄스 애니메이션 시작/정지)"""

# 접이식 박스
class CollapsibleBox(QWidget):
    """접이식 박스 위젯 (부드러운 애니메이션)"""
```

---

## 🎨 UI 테마 시스템

### Catppuccin Mocha 색상 팔레트
```python
# 기본 색상
"#1e1e2e"  # Base (배경)
"#181825"  # Mantle (더 어두운 배경)
"#313244"  # Surface0 (카드 배경)
"#45475a"  # Surface1 (테두리)
"#cdd6f4"  # Text (기본 텍스트)
"#a6adc8"  # Subtext0 (보조 텍스트)

# 액센트 색상
"#89b4fa"  # Blue (Primary)
"#a6e3a1"  # Green (Success)
"#f38ba8"  # Red (Error/Danger)
"#fab387"  # Peach (Warning)
"#cba6f7"  # Mauve (Purple, Picker)
"#f9e2af"  # Yellow (Highlight)
```

### 버튼 스타일 ID
- `#primary` - 파란색 그라데이션
- `#success` - 녹색 그라데이션
- `#danger` - 빨간색 그라데이션
- `#warning` - 주황색 그라데이션
- `#picker` - 보라색 대형 버튼
- `#icon_btn` - 투명 아이콘 버튼

---

## ⚠️ 코딩 규칙 및 주의사항

### 1. **한글 지원**
- 모든 UI 텍스트와 주석은 **한국어**로 작성
- docstring은 한국어 설명 포함

### 2. **타입 힌트**
```python
def generate_alternatives(self, element_info: Dict) -> List[XPathAlternative]:
    """요소 정보로부터 여러 XPath 대안 생성"""
```

### 3. **스레드 안전성**
```python
# RLock 사용 (재진입 가능)
from threading import RLock
self._lock = RLock()

with self._lock:
    # 스레드 안전한 작업
```

### 4. **PyQt6 시그널/슬롯**
```python
# 시그널 정의
class Worker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(dict)

# 슬롯 연결
self.btn_test.clicked.connect(self._test_xpath)
```

### 5. **iframe 처리 패턴**
```python
# 프레임 전환
if not self.switch_to_frame_by_path(frame_path):
    return False

# 작업 수행
try:
    element = self.driver.find_element(By.XPATH, xpath)
finally:
    # 메인 프레임으로 복귀
    self.driver.switch_to.default_content()
```

### 6. **XPath 이스케이프**
```python
def _escape_xpath_text(self, text: str) -> str:
    if '"' in text and "'" in text:
        # concat 함수 사용
        parts = []
        for segment in text.split('"'):
            if segment:
                parts.append(f'"{segment}"')
        return 'concat(' + ', '.join(parts) + ')'
    elif '"' in text:
        return f"'{text}'"
    else:
        return f'"{text}"'
```

---

## 📝 코드 작성 가이드

### 새로운 기능 추가 시
1. 관련 모듈에 기능 구현
2. `xpath_config.py`에 필요한 필드 추가 (기본값 필수)
3. 메인 애플리케이션에 UI 연동
4. `from_dict`에서 하위 호환성 처리

### XPath 관련 기능
```python
# 좋은 예: 안정적인 XPath 패턴
'//*[@id="login"]'                    # ID 기반 (최상)
'//button[@data-action="submit"]'     # data-* 속성
'//input[@name="email"]'              # name 속성
'//button[contains(@class, "btn")]'   # class 포함
'//button[contains(text(), "로그인")]' # 텍스트 포함

# 나쁜 예: 취약한 XPath 패턴
'/html/body/div[1]/div[3]/button[2]'  # 절대 경로 + 인덱스 (취약)
```

### AI 응답 형식
```json
{
    "xpath": "추천 XPath",
    "confidence": 0.85,
    "explanation": "이유 설명",
    "alternatives": ["대안 1", "대안 2"]
}
```

---

## 🔧 상수 및 설정값

### xpath_constants.py
```python
APP_VERSION = "v4.2"
APP_TITLE = "티켓 사이트 XPath 탐색기 v4.2"

# UI 상수
BROWSER_CHECK_INTERVAL = 2000   # ms - 브라우저 상태 확인 주기
SEARCH_DEBOUNCE_MS = 300        # ms - 검색 입력 디바운스
WORKER_WAIT_TIMEOUT = 2000      # ms - 워커 종료 대기
MAX_FRAME_DEPTH = 5             # 프레임 재귀 탐색 최대 깊이
FRAME_CACHE_DURATION = 2.0      # 프레임 캐시 유효 시간 (초)
HISTORY_MAX_SIZE = 50           # Undo/Redo 최대 저장 개수
```

### 사이트 프리셋
- 인터파크 (Cloudflare Turnstile 보호)
- 멜론티켓 (카카오/멜론ID 로그인)
- YES24 티켓
- 티켓링크 (봇 감지 주의)
- 네이버 예약

---

## 🧪 테스트 및 실행

### 실행
```bash
python "xpath 조사기(모든 티켓 사이트).py"
```

### 빌드
```bash
pyinstaller xpath_explorer.spec
# 결과: dist/XPathExplorer_v4.2.exe
```

### 의존성
```bash
# 필수
pip install PyQt6 selenium undetected-chromedriver webdriver-manager

# AI (선택)
pip install openai google-genai

# Playwright (선택)
pip install playwright && playwright install chromium
```

---

## 🔗 AI API 설정

### 환경변수
```bash
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=...
```

### 설정 파일
```
~/.xpath_explorer/ai_config.json
{
    "provider": "gemini",
    "model": "gemini-flash-latest",
    "gemini_api_key": "..."
}
```

---

## 🚫 금지 사항

1. **`PICKER_SCRIPT` 수정 금지** - 브라우저 요소 선택 핵심 로직
2. **메인 파일명 변경 금지** - `xpath 조사기(모든 티켓 사이트).py`
3. **외부 서비스 호출 시 rate limit 고려**
4. **기존 필드 삭제로 하위 호환성 깨기 금지**
5. **메인 스레드에서 장시간 blocking 작업 금지**

---

## 📌 자주 묻는 질문

### Q: 새로운 티켓 사이트 프리셋을 추가하려면?
A: `xpath_constants.py`의 `SITE_PRESETS` 딕셔너리에 추가

### Q: XPath 최적화 전략을 변경하려면?
A: `xpath_optimizer.py`의 `strategy_weights` 딕셔너리 수정

### Q: AI 모델을 변경하려면?
A: `xpath_ai.py`의 `configure(api_key, model, provider)` 메서드 사용

### Q: 새로운 커스텀 위젯을 추가하려면?
A: `xpath_widgets.py`에 위젯 클래스 추가, `xpath_styles.py`에 스타일 정의

### Q: Toast 알림을 표시하려면?
```python
self.toast.show_toast("성공!", "success", 3000)
self.toast.show_toast("경고!", "warning", 3000)
self.toast.show_toast("오류!", "error", 3000)
```

---

## Module Split Update (v4.2)

- Legacy entrypoint remains: `xpath �����(��� Ƽ�� ����Ʈ).py`
- Main app class is now composed from package modules:
  - `xpath_explorer/main_window.py`
  - `xpath_explorer/runtime.py`
  - `xpath_explorer/mixins/ui_mixin.py`
  - `xpath_explorer/mixins/browser_mixin.py`
  - `xpath_explorer/mixins/data_mixin.py`
  - `xpath_explorer/mixins/tools_mixin.py`

Implementation rule:
- Add new `XPathExplorer` methods to the correct mixin by responsibility.
- Keep launch/API compatibility by preserving the legacy entrypoint wrapper.
