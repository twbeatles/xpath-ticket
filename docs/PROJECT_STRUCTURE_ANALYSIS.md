# XPath Explorer 프로젝트 구조 분석 (2026-03-09)

## 1. 목적
- 이 문서는 현재 코드베이스 기준의 실제 구조와 운영 체크 포인트를 요약합니다.
- 기준 원칙은 `코드 > 자동 점검 스크립트 > 문서`입니다.

## 2. 실행/패키징 기준선
- 실행 엔트리포인트: `xpath 조사기(모든 티켓 사이트).py` (레거시 래퍼)
- 실제 앱 조립: `xpath_explorer/main_window.py`
- 배포 스펙: `packaging/pyinstaller/xpath_explorer.spec`
- 빌드 명령: `pyinstaller packaging/pyinstaller/xpath_explorer.spec`

## 3. 패키지 구조 (실제 경로)

```text
xpath_explorer/
├─ main_window.py
├─ runtime.py
├─ core/
├─ browser/
│  ├─ browser.py
│  ├─ playwright.py
│  └─ dom_export.py
├─ workers/
│  └─ background.py
├─ mixins/
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
- `main_window.py`: 서비스 객체 조립 + UI 초기 부팅
- `mixins/*.py`: UI/브라우저/데이터/도구 기능 분리
- `browser/browser.py`: Selenium 기반 검증/프레임/창 복구
- `browser/playwright.py`: Playwright 기반 보조 자동화/스캔
- `workers/background.py`: QThread 워커(검증/배치/미리보기/AI)
- `tools/ai.py`: OpenAI/Gemini 통합 + 설정 저장/로드
- `analysis/*.py`: diff/통계 관리
- `state/history.py`: Undo/Redo 스냅샷 관리

## 5. 정합성 점검 루틴

### 문서/코드 동기화
```bash
python scripts/check_docs_sync.py --strict-warnings
```

### 인코딩/모지바케 점검
```bash
python scripts/check_encoding_health.py
```

### 타입 진단(pyright/pylance 기준선)
```bash
pyright xpath_explorer tests scripts "xpath 조사기(모든 티켓 사이트).py"
```

### 품질 일괄 점검
```bash
python scripts/run_quality_checks.py --strict-doc-warnings --smoke-release
```

## 6. 스펙 파일 정합성 포인트
- `packaging/pyinstaller/xpath_explorer.spec`는 `ENTRYPOINT_CANDIDATES`로 래퍼/패키지 엔트리포인트를 모두 지원합니다.
- `collect_submodules("xpath_explorer")`를 사용해 분할된 패키지 구조를 빌드 수집합니다.
- `qt_excludes`에서 TLS 라이브러리(`libcrypto`, `libssl`)를 제외하지 않는 정책을 유지합니다.
- 선택 의존성(`openai`, `google.genai`, `playwright`)은 릴리즈 스모크에서 import 상태를 점검합니다.

## 7. 인코딩/Pylance 재발 방지 설정
- `.editorconfig`: `charset = utf-8`
- `.vscode/settings.json`:
  - `files.encoding = utf8`
  - `files.autoGuessEncoding = false`
  - `python.analysis.diagnosticMode = workspace`
- `pyrightconfig.json`:
  - include: `xpath_explorer`, `tests`, `scripts`, 레거시 엔트리포인트
  - exclude: `archive`, `__pycache__`, `.pytest_cache`, `build`, `dist`
  - `typeCheckingMode = basic`, `pythonVersion = 3.10`

## 8. 운영 메모
- `archive/`는 보관 영역으로 타입 진단 기본 대상에서 제외합니다.
- 워커/브라우저 타입은 테스트 더블과의 호환성을 우선해 계약을 완화합니다.
- 문서와 코드가 어긋나면 `check_docs_sync.py`를 릴리즈 차단 신호로 취급합니다.
