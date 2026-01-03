# -*- mode: python ; coding: utf-8 -*-
"""
XPath Explorer v3.3 - PyInstaller Spec File
빌드 명령: pyinstaller xpath_explorer.spec
"""

import sys
from PyInstaller.utils.hooks import collect_submodules

# 히든 임포트 수집
hiddenimports = [
    # 사용자 모듈
    'xpath_constants',
    'xpath_styles',
    'xpath_config',
    'xpath_widgets',
    'xpath_browser',
    'xpath_workers',
    'xpath_codegen',      # v3.3 신규
    'xpath_statistics',   # v3.3 신규
    'xpath_playwright',   # Playwright 지원
    
    # PyQt6 관련
    'PyQt6',
    'PyQt6.QtWidgets',
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    
    # Selenium 관련
    'selenium',
    'selenium.webdriver',
    'selenium.webdriver.chrome.service',
    'selenium.webdriver.chrome.options',
    'selenium.webdriver.common.by',
    'selenium.webdriver.support.ui',
    'selenium.webdriver.support.expected_conditions',
    
    # UC Driver
    'undetected_chromedriver',
    
    # Playwright 관련 (선택적)
    'playwright',
    'playwright.sync_api',
    
    # 표준 라이브러리
    'logging',
    'json',
    'pathlib',
]

# 제외할 모듈 (빌드 크기 최적화)
excludes = [
    'matplotlib',
    'numpy',
    'pandas',
    'scipy',
    'tkinter',
    'PIL',
    'cv2',
    'tensorflow',
    'torch',
    'IPython',
    'notebook',
    'pytest',
    'unittest',
]

block_cipher = None

a = Analysis(
    ['xpath 조사기(모든 티켓 사이트).py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='XPathExplorer_v3.3',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
    # Windows 버전 정보
    version_info=None,
)
