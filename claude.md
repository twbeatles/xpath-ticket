# 🧠 Claude AI 지침서 - XPath Explorer

> 이 문서는 Anthropic Claude AI가 XPath Explorer 프로젝트를 이해하고 효과적으로 지원하기 위한 포괄적 가이드입니다.

---

## 🎯 프로젝트 정의

**XPath Explorer v4.2**는 티켓 사이트 웹 자동화를 위한 전문 도구로, 다음 핵심 기능을 제공합니다:

- **🔍 요소 탐색**: 실시간 XPath/CSS 셀렉터 추출
- **🤖 AI 지원**: 자연어 기반 XPath 생성 (OpenAI/Google GenAI)
- **⚡ 최적화**: 안정성 기반 XPath 대안 제안
- **📊 분석**: 요소 변경 감지 (Diff), 테스트 통계
- **🔄 히스토리**: 무제한 Undo/Redo
- **🖼️ 스크린샷**: 요소별 스크린샷 저장

---

## 📂 파일별 책임 및 의존성

| 파일 | 책임 | LOC | 의존 |
|------|------|-----|------|
| `xpath 조사기(모든 티켓 사이트).py` | 메인 GUI, 이벤트 핸들링 | ~2900 | 모든 모듈 |
| `xpath_browser.py` | Selenium WebDriver 관리 | ~813 | xpath_constants |
| `xpath_playwright.py` | Playwright 브라우저 제어 | ~700 | xpath_constants |
| `xpath_ai.py` | AI API 통합 (OpenAI/Google GenAI) | ~481 | - |
| `xpath_optimizer.py` | XPath 최적화 엔진 | ~363 | - |
| `xpath_diff.py` | 요소 변경 감지 | ~423 | - |
| `xpath_history.py` | Undo/Redo 관리 | ~275 | xpath_constants |
| `xpath_config.py` | 데이터 모델 | ~187 | xpath_constants |
| `xpath_constants.py` | 상수, 프리셋, 스크립트 | ~553 | - |
| `xpath_widgets.py` | 커스텀 PyQt6 위젯 | ~736 | - |
| `xpath_styles.py` | CSS 스타일시트 | ~869 | - |
| `xpath_workers.py` | 백그라운드 스레드 | ~160 | - |
| `xpath_codegen.py` | 코드 생성 (Python/JS) | ~260 | - |
| `xpath_statistics.py` | 테스트 통계 관리 | ~250 | - |

---

## 🔧 핵심 아키텍처

### 데이터 흐름
```
사용자 입력
    ↓
[XPathExplorer] ─────────────────────────────────────
    │                                               │
    ├──→ [BrowserManager] ──→ Selenium/Playwright  │
    │         ↓                                    │
    │    [PickerWatcher] ← PICKER_SCRIPT 주입      │
    │                                               │
    ├──→ [XPathOptimizer] ──→ 대안 생성            │
    │                                               │
    ├──→ [XPathAIAssistant] ──→ AI API             │
    │                                               │
    ├──→ [HistoryManager] ──→ Undo/Redo            │
    │                                               │
    ├──→ [XPathDiffAnalyzer] ──→ 스냅샷 비교       │
    │                                               │
    └──→ [SiteConfig] ──→ JSON 저장/로드           │
─────────────────────────────────────────────────────
```

### XPathItem 생명주기
```
1. 생성: Picker로 요소 선택 또는 수동 입력 또는 AI 생성
2. 최적화: XPathOptimizer가 대안 생성 (alternatives 필드)
3. 스냅샷: DiffAnalyzer가 현재 상태 저장 (element_attributes)
4. 검증: 브라우저에서 유효성 테스트 (test_count, success_count 업데이트)
   - 단일/전체/배치 검증은 동일한 결과 처리 경로를 사용해야 함
   - 성공 시 element_attributes 갱신 + diff_analyzer.save_snapshot 호출
5. 저장: SiteConfig에 추가, JSON 내보내기
6. 업데이트: HistoryManager에 변경사항 기록
7. 기준점 재설정: preset/new/open 직후 history baseline 재초기화
```

---

## 🎨 UI 테마 시스템 (Catppuccin Mocha)

### 색상 팔레트
```python
# xpath_styles.py에서 사용되는 주요 색상

# 기본 색상
BASE        = "#1e1e2e"   # 메인 배경
MANTLE      = "#181825"   # 더 어두운 배경
SURFACE0    = "#313244"   # 카드 배경
SURFACE1    = "#45475a"   # 테두리
SURFACE2    = "#585b70"   # hover 테두리
TEXT        = "#cdd6f4"   # 기본 텍스트
SUBTEXT0    = "#a6adc8"   # 보조 텍스트
OVERLAY0    = "#6c7086"   # 비활성 텍스트

# 액센트 색상
BLUE        = "#89b4fa"   # Primary (버튼, 링크)
LAVENDER    = "#b4befe"   # Hover
GREEN       = "#a6e3a1"   # Success
RED         = "#f38ba8"   # Error/Danger
PEACH       = "#fab387"   # Warning
MAUVE       = "#cba6f7"   # Picker 버튼
PINK        = "#f5c2e7"   # Gradient end
YELLOW      = "#f9e2af"   # Highlight
TEAL        = "#94e2d5"   # Secondary accent
SKY         = "#89dceb"   # Alternative accent
```

### 버튼 ObjectName 스타일
```python
# 메인 앱에서 사용 방법:
btn = QPushButton("텍스트")
btn.setObjectName("primary")  # 파란색 그라데이션

# 사용 가능한 ObjectName:
# "primary"  - 파란색 그라데이션 (메인 액션)
# "success"  - 녹색 그라데이션 (성공/저장)
# "danger"   - 빨간색 그라데이션 (삭제/위험)
# "warning"  - 주황색 그라데이션 (경고/테스트)
# "picker"   - 보라색 대형 버튼 (요소 선택)
# "icon_btn" - 투명 아이콘 버튼
# "action_btn" - 테두리 있는 액션 버튼
```

### 입력 필드 스타일
```python
# 특수 입력 필드 ObjectName:
# "search_input"    - 검색창 (왼쪽 패딩 확대)
# "url_input_large" - URL 입력창 (큰 폰트)
```

---

## 🔌 브라우저 관리 상세 (xpath_browser.py)

### BrowserManager 핵심 메서드
```python
class BrowserManager:
    def __init__(self):
        self.driver = None
        self.current_frame_path = ""   # 현재 활성 프레임 경로
        self.frame_cache = []          # 캐시된 프레임 목록
        self.frame_cache_time = 0      # 캐시 생성 시간
        self.FRAME_CACHE_DURATION = 2.0  # 캐시 유효 시간 (초)
    
    # 드라이버 생성 (봇 탐지 우회)
    def create_driver(self, use_undetected: bool = True) -> bool:
        """undetected-chromedriver 또는 표준 Chrome 사용"""
    
    # 연결 상태 확인 (자동 복구)
    def is_alive(self) -> bool:
        """NoSuchWindowException 시 자동으로 다른 윈도우로 복구"""
    
    # iframe 관련
    def get_all_frames(self, max_depth: int = 5) -> List[tuple]:
        """모든 iframe 재귀 탐색 (캐시 적용)"""
    
    def switch_to_frame_by_path(self, frame_path: str) -> bool:
        """경로로 프레임 전환 (예: 'ifrmSeat/ifrmSeatDetail')"""
    
    def find_element_in_all_frames(self, xpath: str) -> Tuple[Optional[Any], str]:
        """모든 프레임에서 요소 검색, (element, frame_path) 반환"""
    
    # Picker 관련
    def start_picker(self, overlay_mode: bool = False):
        """모든 iframe에 PICKER_SCRIPT 주입"""
    
    def get_picker_result(self) -> Optional[Dict]:
        """모든 프레임에서 선택 결과 검색"""
    
    def is_picker_active(self) -> bool:
        """모든 프레임에서 피커 활성 상태 확인"""
    
    # 요소 정보
    def get_element_info(self, xpath: str, frame_path: str = None) -> Optional[Dict]:
        """요소 상세 정보 (Diff 분석용)"""
        # 반환값:
        # {
        #     'found': bool,
        #     'tag': str,
        #     'id': str,
        #     'name': str,
        #     'class': str,
        #     'text': str,
        #     'attributes': dict,
        #     'count': int,
        #     'parent_tag': str,
        #     'parent_id': str,
        #     'parent_class': str,
        #     'index': int
        # }
```

### 프레임 캐시 무효화 시점
```python
# 다음 상황에서 _invalidate_frame_cache() 호출됨:
# 1. navigate() - 페이지 이동 시
# 2. 프레임 스캔 오류 시
# 3. 윈도우 복구 시
```

---

## 📦 커스텀 위젯 패턴 (xpath_widgets.py)

### NoWheel 위젯
```python
# 스크롤 영역에서 ComboBox/SpinBox 값이 실수로 변경되는 것 방지
class NoWheelComboBox(QComboBox):
    def wheelEvent(self, event):
        event.ignore()  # 부모에게 전달

class NoWheelSpinBox(QSpinBox):
    def wheelEvent(self, event):
        event.ignore()
```

### ToastWidget 사용법
```python
# 메인 윈도우에서 초기화
self.toast = ToastWidget(self)

# 메시지 표시
self.toast.show_toast("성공!", "success", 3000)  # 3초
self.toast.show_toast("경고!", "warning", 5000)  # 5초
self.toast.show_toast("오류!", "error", 0)       # 자동 닫힘 없음

# 테마: "success", "warning", "error", "info"
```

### AnimatedStatusIndicator
```python
# 연결 상태 인디케이터 (펄스 애니메이션)
self.status_indicator = AnimatedStatusIndicator()

# 상태 변경
self.status_indicator.set_connected(True)   # 녹색 펄스
self.status_indicator.set_connected(False)  # 빨간색 고정

# 정리
self.status_indicator.cleanup()  # 타이머 정지
```

### CollapsibleBox
```python
# 접이식 박스 (URL 패널 등에 사용)
self.url_collapsible = CollapsibleBox("🌐 URL 주소창", expanded=True)

# 컨텐츠 설정
content = QWidget()
layout = QHBoxLayout(content)
# ... 위젯 추가
self.url_collapsible.setContentLayout(layout)

# 시그널
self.url_collapsible.toggled.connect(self._on_url_panel_toggled)
```

---

## 🔄 히스토리 관리 상세 (xpath_history.py)

### HistoryManager 사용 패턴
```python
# 초기화 (앱 시작 시)
self.history_manager = HistoryManager(max_history=50)
self.history_manager.initialize(self.config.items)

# 변경 전 상태 저장
self.history_manager.push_state(
    items=self.config.items,
    action="update",        # "add", "update", "delete", "batch_update"
    item_name="login_btn",
    description="XPath 변경"
)

# 변경 수행
self.config.items[0].xpath = "//new/xpath"

# Undo
if self.history_manager.can_undo():
    restored_dicts = self.history_manager.undo()
    # XPathItem 객체로 복원 필요

# Redo
if self.history_manager.can_redo():
    restored_dicts = self.history_manager.redo()
```

### 메모리 최적화
```python
# 히스토리 저장 시 대용량 필드 제외
EXCLUDE_FIELDS = {'alternatives', 'element_attributes', 'screenshot_path'}
```

---

## 🔍 Diff 분석기 상세 (xpath_diff.py)

### XPathDiffAnalyzer 사용
```python
self.diff_analyzer = XPathDiffAnalyzer()

# 스냅샷 저장 (검증 성공 시)
element_info = self.browser.get_element_info(xpath)
self.diff_analyzer.save_snapshot(item.name, element_info)

# 비교
result = self.diff_analyzer.compare_element(stored_item, current_info)
# result.status: "unchanged", "modified", "missing", "found"
# result.changes: ["class 추가: new-class", "ID 변경: old → new"]

# 리포트 생성
results = self.diff_analyzer.compare_all(items, self.browser)
report = self.diff_analyzer.generate_diff_report(results)
```

### 스냅샷 크기 제한
```python
MAX_SNAPSHOTS = 100  # 최대 스냅샷 저장 개수
# 초과 시 오래된 것부터 자동 제거
```

---

## ⚙️ 주요 상수 (xpath_constants.py)

### UI/성능 상수
```python
BROWSER_CHECK_INTERVAL = 2000   # ms - 브라우저 상태 확인 주기
SEARCH_DEBOUNCE_MS = 300        # ms - 검색 입력 디바운스
DEFAULT_WINDOW_SIZE = (1400, 900)
MAX_FRAME_DEPTH = 5             # 프레임 재귀 탐색 최대 깊이
FRAME_CACHE_DURATION = 2.0      # 프레임 캐시 유효 시간 (초)
WORKER_WAIT_TIMEOUT = 2000      # ms - 워커 종료 대기
HISTORY_MAX_SIZE = 50           # Undo/Redo 최대 저장 개수
STATISTICS_SAVE_INTERVAL = 5.0  # 통계 저장 간격 (초)
```

### PICKER_SCRIPT 구조
```javascript
// 주요 기능:
// 1. __pickerActive - 활성화 상태
// 2. __pickerResult - 선택 결과
// 3. __pickerLocked - 선택 고정 상태
// 4. __pickerCleanup - 정리 함수
// 5. getXPath(element) - XPath 생성
// 6. getCssSelector(element) - CSS 셀렉터 생성
```

### STEALTH_SCRIPT
```javascript
// 봇 탐지 우회:
// 1. navigator.webdriver 숨김
// 2. window.chrome 속성 추가
// 3. permissions 위장
// 4. languages 설정
// 5. plugins 위장
// 6. canvas fingerprint 랜덤화
// 7. WebGL 렌더러 위장
// 8. hardwareConcurrency/deviceMemory 설정
```

---

## 🎨 코드 스타일 가이드

### 명명 규칙
```python
# 클래스: PascalCase
class XPathExplorer(QMainWindow):
    pass

# 함수/메서드: snake_case, private은 _접두사
def _create_browser_panel(self):
    pass

# 상수: UPPER_SNAKE_CASE
MAX_FRAME_DEPTH = 5
HISTORY_MAX_SIZE = 50

# 변수: snake_case
elem_id = element_info.get('id', '')
```

### PyQt6 패턴
```python
# 시그널 정의
class Worker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(dict)
    
    def run(self):
        # 백그라운드 작업
        self.progress.emit(50)
        self.finished.emit(result)

# 슬롯 연결
self.worker.finished.connect(self._on_work_finished)
```

### 예외 처리
```python
try:
    element = self.driver.find_element(By.XPATH, xpath)
except NoSuchElementException:
    return {'found': False, 'msg': '요소 없음'}
except StaleElementReferenceException:
    continue  # 루프에서 다음 요소로
except WebDriverException as e:
    logger.error(f"WebDriver 오류: {e}")
    return None
```

---

## 🔒 보안 고려사항

### v4.2에서 수정된 보안 이슈
1. **LocalStorage XSS 취약점** - 입력 검증 추가
2. **네트워크 리스너 메모리 누수** - 적절한 cleanup 구현
3. **스레드 동기화** - PickerWatcher 개선, RLock 사용

### API 키 관리
```python
# 우선순위: 인자 > 설정 파일 > 환경변수
self._api_key = api_key or self._config.get(f'{self._provider}_api_key')

# 설정 파일 위치
config_path = Path.home() / '.xpath_explorer' / 'ai_config.json'

# 로그 파일 위치
log_path = Path.home() / '.xpath_explorer' / 'debug.log'
```

---

## 🧩 일반적인 수정 시나리오

### 1. 새로운 사이트 프리셋 추가
```python
# xpath_constants.py의 SITE_PRESETS에 추가
"새사이트": {
    "name": "새사이트 티켓",
    "url": "https://new-site.com",
    "login_url": "https://new-site.com/login",
    "description": "사이트 설명",
    "items": [
        {"name": "login_id", "xpath": '//input[@id="id"]', 
         "category": "login", "desc": "아이디 입력"},
        # ...
    ]
}
```

### 2. XPathItem에 새 필드 추가
```python
# 1. xpath_config.py에 필드 추가 (기본값 필수!)
@dataclass
class XPathItem:
    new_field: str = ""  # 기본값 필수 (하위 호환성)

# 2. from_dict에서 로드 처리
new_field=item_data.get('new_field', '')

# 3. 히스토리 제외 필드 확인 (필요시)
# xpath_history.py의 EXCLUDE_FIELDS 확인
```

### 3. AI 프롬프트 수정
```python
# xpath_ai.py의 system_prompt 수정
system_prompt = """당신은 웹 자동화 전문가입니다.
# 새로운 지침 추가...
"""
```

### 4. 새로운 커스텀 위젯 추가
```python
# 1. xpath_widgets.py에 위젯 클래스 정의
class NewWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("new_widget")
        # ...

# 2. xpath_styles.py에 스타일 추가
"""
QFrame#new_widget {
    background: ...;
    border: ...;
}
"""
```

---

## 📊 로깅 시스템

```python
# 로거 설정 (메인 앱에서)
import logging
logger = logging.getLogger('XPathExplorer')

# 사용 예
logger.info("브라우저 연결됨")
logger.warning("요소를 찾을 수 없음: %s", xpath)
logger.error("WebDriver 오류: %s", e)
logger.debug("프레임 전환: %s", frame_path)

# 로그 레벨
# 콘솔: INFO 이상
# 파일: DEBUG 이상 (~/.xpath_explorer/debug.log)
```

---

## ✅ 코드 리뷰 체크리스트

- [ ] 타입 힌트가 모든 함수에 있는가?
- [ ] docstring이 한국어로 작성되었는가?
- [ ] try-except로 적절히 예외 처리되었는가?
- [ ] UI 업데이트가 메인 스레드에서 이루어지는가?
- [ ] 하위 호환성이 유지되는가? (기존 JSON 로드 가능)
- [ ] 메모리 누수 가능성이 없는가? (cleanup, deleteLater 확인)
- [ ] 브라우저 자동화 코드에 적절한 대기/복구가 있는가?
- [ ] 프레임 전환 후 default_content로 복귀하는가?
- [ ] 스레드 안전한가? (lock 사용 확인)
- [ ] 검증 결과가 item 통계와 StatisticsManager에 중복/누락 없이 동일 반영되는가?
- [ ] Diff 스냅샷이 성공 검증 경로에서 실제로 축적되는가?
- [ ] 코드 생성 템플릿이 중괄호 문자열로 인해 런타임 KeyError를 내지 않는가?

---

## 🚨 주의사항

### 절대 하지 말아야 할 것
1. **`PICKER_SCRIPT` 수정** - 브라우저 요소 선택 핵심 로직
2. **메인 스레드에서 장시간 blocking 작업** (QThread 사용)
3. **API 키를 코드에 하드코딩**
4. **기존 필드 삭제로 하위 호환성 깨기**
5. **NoWheel 위젯 대신 일반 위젯 사용** (UX 저하)

### 주의가 필요한 부분
1. **iframe 처리** - `switch_to_frame()` 후 반드시 `switch_to_default_content()` 필요
2. **JavaScript 실행** - `driver.execute_script()` 반환값 타입 확인
3. **셀렉터 이스케이프** - 특수문자(따옴표, #, [, ]) 처리
4. **프레임 캐시** - 페이지 이동 시 `_invalidate_frame_cache()` 호출

---

## 💡 개선 제안 시 고려사항

1. **사용자 경험**: 티켓 예매 시 시간이 중요하므로 속도 우선
2. **안정성**: 사이트 구조 변경에 강한 XPath 권장 (인덱스 기반 피하기)
3. **범용성**: 특정 사이트에 종속되지 않는 설계
4. **접근성**: 한국 사용자 대상, 한국어 UI 유지
5. **디버깅**: 충분한 로깅으로 문제 추적 용이하게

---

## 🔧 디버깅 팁

### 브라우저 연결 문제
```python
# 1. is_alive() 확인
if not self.browser.is_alive():
    logger.error("브라우저 연결 끊김")
    
# 2. 윈도우 핸들 확인
handles = self.driver.window_handles
logger.debug(f"열린 윈도우: {len(handles)}개")

# 3. 프레임 상태 확인
logger.debug(f"현재 프레임: {self.browser.current_frame_path}")
```

### XPath 검증 문제
```python
# 1. 요소 개수 확인
count = self.browser.count_elements(xpath)
logger.debug(f"매칭 요소: {count}개")

# 2. 프레임 내 검색
element, frame_path = self.browser.find_element_in_all_frames(xpath)
logger.debug(f"발견 프레임: {frame_path}")
```

---

## Performance Refactor Notes (v4.2)

### List Rendering Path
- Main list uses `QTableView` + `XPathItemTableModel` + `XPathFilterProxyModel`.
- Filtering must be applied by proxy state (`category/search/favorites/tag`) and `invalidateFilter()`.
- Avoid per-row widget creation in the main list path.

### Validation Session Path
- Batch/loop validation should use:
  - `session = browser.begin_validation_session()`
  - repeated `validate_xpath(..., session=session)`
  - `browser.end_validation_session(session)` in `finally`
- Prefer `preferred_frame` and session/global frame hints before full recursive scan.

### Statistics + Diff Path
- `StatisticsManager.record_test()` must remain non-blocking for UI paths.
- Use `shutdown()` during application close to guarantee final flush.
- In `_record_validation_outcome`, request full attributes only when snapshot baseline is missing:
  - `need_snapshot = not diff_analyzer.has_snapshot(name) or not item.element_attributes`
  - call `get_element_info(..., include_attributes=need_snapshot)`

### Perf Metrics
- Keep perf span names stable:
  - `ui.refresh_table`
  - `ui.update_live_preview`
  - `browser.validate_xpath`
  - `worker.batch_validate_loop`
  - `stats.record_test`
- Emit perf summary at shutdown via `log_perf_summary()`.

### Guardrails
- Do not modify `PICKER_SCRIPT`.
- Maintain JSON backward compatibility.
- Keep UI labels/shortcuts behavior-compatible unless explicitly requested.
