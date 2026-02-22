# -*- mode: python ; coding: utf-8 -*-
"""
XPath Explorer v4.2 - PyInstaller spec (optimized).
Build: pyinstaller xpath_explorer.spec
"""

import os
from PyInstaller.utils.hooks import collect_submodules
os.environ['SETUPTOOLS_USE_DISTUTILS'] = 'stdlib'

# ============================================================================
# 히든 임포트 (필수만)
# ============================================================================
hiddenimports = [
    # 프로젝트 모듈
    'xpath_ai', 'xpath_diff', 'xpath_history', 'xpath_optimizer',
    'xpath_constants', 'xpath_styles', 'xpath_config', 'xpath_widgets',
    'xpath_browser', 'xpath_workers', 'xpath_codegen', 'xpath_statistics',
    'xpath_table_model', 'xpath_filter_proxy',

    # OpenAI
    'openai',

    # Google GenAI (신규)
    'google.genai', 'google.genai.types',

    # Playwright
    'playwright', 'playwright.sync_api', 'playwright._impl', 'pyee',
    
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
    ['xpath 조사기(모든 티켓 사이트).py'],
    pathex=['.'],
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
    'opengl32sw', 'd3dcompiler', 'libcrypto', 'libssl',
]
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
    upx=False,      # UPX 압축 (upx.exe 필요)
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # GUI 앱
    disable_windowed_traceback=False,
    icon=None,      # 아이콘: 'icon.ico'
)

# ============================================================================
# 빌드 팁:
# - UPX 설치: https://upx.github.io (PATH에 추가)
# - 예상 크기: 40-60MB (UPX 적용)
# - AI 기능: openai, google-genai 별도 설치
# - Playwright: pip install playwright && playwright install chromium
# ============================================================================
