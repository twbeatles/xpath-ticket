# XPath Explorer 프로젝트 구조 분석 (2026-03-12)

## 1. 목적
- 현재 코드베이스의 실제 구조, 실행 경로, 품질 게이트, 배포 경로를 한 문서에서 빠르게 파악하기 위한 요약 문서입니다.
- 기준 우선순위는 `코드 > 자동 점검 스크립트 > 문서`입니다.

## 2. 실행/엔트리포인트 구조
- 레거시 실행 래퍼: `xpath 조사기(모든 티켓 사이트).py`
- 패키지 실행 진입점: `xpath_explorer/__main__.py`
- 실제 앱 조립: `xpath_explorer/main_window.py`
- headless/CI Qt 호환 계층: `xpath_explorer/qt_compat.py`
- PyInstaller 스펙: `packaging/pyinstaller/xpath_explorer.spec`

실행 예시:

```bash
python "xpath 조사기(모든 티켓 사이트).py"
python -m xpath_explorer
```

빌드 예시:

```bash
pyinstaller packaging/pyinstaller/xpath_explorer.spec
```

## 3. 패키지 구조

```text
xpath_explorer/
├─ __init__.py
├─ __main__.py
├─ main_window.py
├─ qt_compat.py
├─ runtime.py
├─ core/
├─ browser/
│  ├─ browser.py
│  ├─ playwright.py
│  └─ dom_export.py
├─ workers/
│  └─ background.py
├─ mixins/
│  ├─ __init__.py
│  ├─ ui_mixin.py
│  ├─ browser_mixin.py
│  ├─ data_mixin.py
│  └─ tools_mixin.py
├─ tools/
│  ├─ ai.py
│  ├─ codegen.py
│  └─ optimizer.py
├─ analysis/
│  ├─ diff.py
│  └─ statistics.py
├─ state/
│  └─ history.py
└─ ui/
   ├─ widgets.py
   ├─ table_model.py
   ├─ filter_proxy.py
   └─ styles.py
```

## 4. 책임 분리 요약
- `main_window.py`: `XPathExplorer` 조합, 초기 상태/타이머/모듈 초기화
- `qt_compat.py`: PyQt6 import와 headless fallback을 분리해 CI 수집 안정성 보장
- `mixins/ui_mixin.py`: 메뉴/패널/편집기/상태 UI 구성
- `mixins/browser_mixin.py`: Selenium 브라우저 연결, 창/프레임, DOM export
- `mixins/data_mixin.py`: 편집기 데이터 바인딩, 히스토리, import/export, 설정 복원
- `mixins/tools_mixin.py`: 배치/시나리오/AI/통계/DOM diff/리포트
- `browser/browser.py`: Selenium 검증 세션, 프레임 힌트, miss cache
- `browser/playwright.py`: Playwright 실행/탐색/DOM 수집
- `workers/background.py`: Validate/Batch/Scenario/AI/QThread 워커
- `runtime.py`: 로거, 오류 텔레메트리, 경로 폴백 로깅

## 5. 품질 게이트

### 로컬 기본 점검

```bash
python scripts/check_docs_sync.py --strict-warnings
python scripts/check_encoding_health.py
pyright xpath_explorer tests scripts "xpath 조사기(모든 티켓 사이트).py"
pytest -q
```

`pyright` 명령이 없으면:

```bash
python -m pyright xpath_explorer tests scripts "xpath 조사기(모든 티켓 사이트).py"
```

### CI 기본 게이트
- 워크플로: `.github/workflows/quality.yml`
- 순서: `check_encoding_health` -> `pyright`
- 트리거: PR, `main`/`master` push
- GitHub Actions에서는 `pytest`를 실행하지 않습니다.

### Qt 테스트 정책
- Qt 런타임이 필요한 테스트는 `pytest.mark.qt`로 분리됩니다.
- 로컬 GUI/Qt 환경에서는 `pytest -q -m qt`로 별도 확인합니다.

## 6. 배포 스펙 정합성
- `packaging/pyinstaller/xpath_explorer.spec`는 다음 엔트리포인트 후보를 사용합니다.
  - `xpath 조사기(모든 티켓 사이트).py`
  - `xpath_explorer/__main__.py`
- `collect_submodules("xpath_explorer")`로 분할 패키지 구조를 자동 수집합니다.
- `xpath_explorer.qt_compat`를 hidden import에 명시해 Qt bootstrap 경로 누락을 방지합니다.
- `qt_excludes`에는 TLS 관련 라이브러리(`libcrypto`, `libssl`)를 넣지 않습니다.
- 선택 의존성(`openai`, `google.genai`, `playwright`)은 빌드 환경에 설치된 경우에만 hidden import로 추가됩니다.

## 7. 인코딩/Pylance 운영 기준
- `.editorconfig`: `charset = utf-8`, `end_of_line = lf`
- `.vscode/settings.json`
  - `files.encoding = utf8`
  - `files.autoGuessEncoding = false`
  - `python.analysis.diagnosticMode = workspace`
- `pyrightconfig.json`
  - include: `xpath_explorer`, `tests`, `scripts`, `xpath 조사기(모든 티켓 사이트).py`
  - exclude: `archive`, `__pycache__`, `.pytest_cache`, `build`, `dist`
- Qt 관련 import는 `TYPE_CHECKING` 분리 또는 `qt_compat.py`를 우선 사용합니다.

## 8. 운영 메모
- `archive/`는 보관 영역이며 정적 분석/기본 점검 대상에서 제외됩니다.
- 문서와 코드가 어긋나면 `scripts/check_docs_sync.py`를 우선 기준으로 수정합니다.
- 릴리즈 전에는 `scripts/run_quality_checks.py --strict-doc-warnings --smoke-release` 실행을 권장합니다.
