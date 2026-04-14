# -*- mode: python ; coding: utf-8 -*-
"""
XPath Explorer v4.2 - PyInstaller spec (optimized).
Build: pyinstaller packaging/pyinstaller/xpath_explorer.spec
"""

import os
import sys
from importlib.util import find_spec
from PyInstaller.utils.hooks import collect_submodules
os.environ['SETUPTOOLS_USE_DISTUTILS'] = 'stdlib'
SPEC_PATH = next((arg for arg in reversed(sys.argv) if str(arg).lower().endswith('.spec')), None)
if SPEC_PATH is None:
    SPEC_PATH = os.path.join(os.getcwd(), 'packaging', 'pyinstaller', 'xpath_explorer.spec')
SPEC_PATH = os.path.abspath(SPEC_PATH)
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(SPEC_PATH), '..', '..'))
ENTRYPOINT_CANDIDATES = [
    os.path.join(ROOT_DIR, 'xpath 조사기(모든 티켓 사이트).py'),
    os.path.join(ROOT_DIR, 'xpath_explorer', '__main__.py'),
]
ENTRYPOINT = next((path for path in ENTRYPOINT_CANDIDATES if os.path.exists(path)), None)
if ENTRYPOINT is None:
    raise FileNotFoundError("No valid entrypoint found for PyInstaller build")


def _module_available(module_name: str) -> bool:
    try:
        return find_spec(module_name) is not None
    except Exception:
        return False

def _collect_optional_hiddenimports(*module_names: str):
    return [name for name in module_names if _module_available(name)]
# ============================================================================
# 히든 임포트 (필수만)
# ============================================================================
hiddenimports = [
    # 프로젝트 모듈
    'xpath_explorer.tools.ai',
    'xpath_explorer.analysis.diff',
    'xpath_explorer.state.history',
    'xpath_explorer.tools.optimizer',
    'xpath_explorer.core.constants',
    'xpath_explorer.ui.styles',
    'xpath_explorer.core.config',
    'xpath_explorer.core.paths',
    'xpath_explorer.qt_compat',
    'xpath_explorer.ui.widgets',
    # tools_mixin에서 Playwright는 동적 import 경로가 있어 hiddenimports에 명시
    'xpath_explorer.browser.browser',
    'xpath_explorer.browser.playwright',
    'xpath_explorer.browser.dom_export',
    'xpath_explorer.workers.background',
    'xpath_explorer.tools.codegen',
    'xpath_explorer.analysis.statistics',
    'xpath_explorer.ui.table_model',
    'xpath_explorer.ui.filter_proxy',
    # PyQt6 (필수)
    'PyQt6.QtWidgets', 'PyQt6.QtCore', 'PyQt6.QtGui',
    
    # Selenium (필수)
    'selenium.webdriver', 'selenium.webdriver.chrome.service',
    'selenium.webdriver.chrome.options', 'selenium.webdriver.common.by',
    'selenium.webdriver.support.ui', 'selenium.webdriver.support.expected_conditions',
    'selenium.common.exceptions',
    
    # UC Driver
    'undetected_chromedriver',
]

# Project package split support: include all submodules under xpath_explorer/.
hiddenimports += collect_submodules('xpath_explorer')
# Optional dependencies: include only when available in build environment.
hiddenimports += _collect_optional_hiddenimports(
    'openai',
    'google.genai',
    'google.genai.types',
    'playwright',
    'playwright.sync_api',
    'playwright._impl',
    'pyee',
)

# ============================================================================
# 제외 모듈 (경량화)
# ============================================================================
excludes = [
    # 데이터 과학 (불필요)
    'matplotlib', 'numpy', 'pandas', 'scipy', 'sklearn',
    
    # 이미지/비디오 (불사용)
    'PIL', 'Pillow', 'cv2', 'opencv',
    
    # ML/AI 대형 라이브러리
    'tensorflow', 'torch', 'keras', 'transformers',
    
    # 개발 도구
    'IPython', 'notebook', 'jupyter', 'pytest', 'unittest', 'sphinx',
    
    # 다른 GUI
    'tkinter', 'wx', 'PySide6', 'PyQt5',
    
    # 웹 프레임워크
    'flask', 'django', 'fastapi', 'aiohttp', 'uvicorn',
    
    # 기타
    'test', 'tests', 'setuptools', 'pip', 'wheel',
    
    # Playwright는 full 기능 지원을 위해 포함 (chromium 설치는 런타임에서 수행)
]

# ============================================================================
# Analysis
# ============================================================================
a = Analysis(
    [ENTRYPOINT],
    pathex=[ROOT_DIR],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

# ============================================================================
# 불필요 Qt 모듈 제거 (경량화 핵심)
# ============================================================================
qt_excludes = [
    'qt5', 'qt6webengine', 'qt6quick', 'qt6qml', 'qt6pdf',
    'qt6designer', 'qt6help', 'qt6sql', 'qt6network',
    'qt6multimedia', 'qt6dbus', 'qt6test', 'qt6xml',
    'qt6positioning', 'qt6sensors', 'qt6serialport',
    'qt6bluetooth', 'qt6nfc', 'qt6webchannel',
    'opengl32sw', 'd3dcompiler',
]
# NOTE:
# Do not add TLS runtime libraries ('libcrypto', 'libssl') to qt_excludes.
# HTTPS smoke checks rely on them in packaged runtime.
a.binaries = [b for b in a.binaries if not any(x in b[0].lower() for x in qt_excludes)]

# 불필요 데이터 제거
a.datas = [d for d in a.datas if not any(x in d[0].lower() for x in ['translations', 'examples'])]

# ============================================================================
# PYZ & EXE
# ============================================================================
pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='XPathExplorer_v4.2',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,      # 기본 비활성(필요 시 True로 변경, upx.exe 필요)
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # GUI 앱
    disable_windowed_traceback=False,
    icon=None,      # 아이콘: 'icon.ico'
)

# ============================================================================
# 빌드 팁:
# - 빌드 전 정합성 점검:
#   python scripts/check_docs_sync.py --strict-warnings
#   python scripts/check_encoding_health.py
#   pyright -p .
#   python scripts/run_quality_checks.py --strict-doc-warnings
# - UPX 설치: https://upx.github.io (PATH에 추가)
# - 예상 크기: 40-60MB (UPX 적용)
# - 선택 기능 포함 빌드: pip install -r requirements/requirements-full.txt
# - repo-local `.venv`를 사용하면 pyright와 빌드 환경 정합성을 맞추기 쉽습니다.
# - AI/Playwright 선택 의존성은 설치된 경우에만 hidden import로 포함
# - Playwright 런타임 브라우저: pip install playwright && playwright install chromium
# ============================================================================

