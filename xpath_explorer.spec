# -*- mode: python ; coding: utf-8 -*-
"""
XPath Explorer v3.6 - PyInstaller Spec File (Optimized)
빌드 명령: pyinstaller xpath_explorer.spec
경량화 최적화 적용
Python 3.14+ 호환
"""

import sys
import os

# Python 3.12+에서 distutils가 표준 라이브러리에서 제거됨
# PyInstaller 훅 충돌 방지를 위해 setuptools의 vendored distutils 사용 강제
os.environ['SETUPTOOLS_USE_DISTUTILS'] = 'stdlib'

from PyInstaller.utils.hooks import collect_submodules

# ============================================================================
# 히든 임포트 (필수 모듈만)
# ============================================================================
hiddenimports = [
    # 사용자 모듈
    'xpath_constants',
    'xpath_styles',
    'xpath_config',
    'xpath_widgets',
    'xpath_browser',
    'xpath_workers',
    'xpath_codegen',
    'xpath_statistics',
    'xpath_playwright',
    
    # PyQt6 (필수 컴포넌트만)
    'PyQt6.QtWidgets',
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    
    # Selenium (필수만)
    'selenium.webdriver',
    'selenium.webdriver.chrome.service',
    'selenium.webdriver.chrome.options',
    'selenium.webdriver.common.by',
    'selenium.webdriver.support.ui',
    'selenium.webdriver.support.expected_conditions',
    'selenium.common.exceptions',
    
    # UC Driver
    'undetected_chromedriver',
    
    # 표준 라이브러리
    'logging',
    'json',
    'pathlib',
    'dataclasses',
]

# ============================================================================
# 제외 모듈 (경량화 - Python 3.12+ 호환)
# ============================================================================
excludes = [
    # 데이터 과학
    'matplotlib', 'numpy', 'pandas', 'scipy', 'sklearn',
    
    # 이미지/비디오
    'PIL', 'Pillow', 'cv2', 'opencv',
    
    # 머신러닝
    'tensorflow', 'torch', 'keras', 'transformers',
    
    # 개발/테스트 도구
    'IPython', 'notebook', 'jupyter', 'pytest', 'unittest', 'sphinx',
    
    # 기타 GUI
    'tkinter', 'wx', 'PySide6', 'PyQt5',
    
    # 웹 프레임워크
    'flask', 'django', 'fastapi', 'aiohttp',
    
    # 불필요한 표준 라이브러리 (Python 3.12+ 호환)
    'test', 'tests',
    # 주의: distutils, setuptools, pip는 제외하지 않음 (PyInstaller 내부 사용)
    
    # Playwright (선택적 - 런타임 설치 권장)
    'playwright',
    'playwright.sync_api',
    'playwright.async_api',
]

# ============================================================================
# Analysis - Python 3.14+ 호환성 개선
# ============================================================================
block_cipher = None

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
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# ============================================================================
# 불필요한 바이너리 제거 (경량화)
# ============================================================================
# Qt 관련 불필요 파일 제거
a.binaries = [b for b in a.binaries if not any(x in b[0].lower() for x in [
    'qt5', 'qt6webengine', 'qt6quick', 'qt6qml', 'qt6pdf',
    'qt6designer', 'qt6help', 'qt6sql', 'qt6network',
    'qt6multimedia', 'qt6dbus', 'qt6test', 'qt6xml',
    'opengl32sw', 'd3dcompiler',
])]

# ============================================================================
# PYZ & EXE
# ============================================================================
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='XPathExplorer_v3.5',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,  # Windows 호환성 (strip 명령 없음)
    upx=True,    # UPX 압축 활성화
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # GUI 앱이므로 콘솔 숨김
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

# ============================================================================
# 빌드 후 정리 팁:
# - dist 폴더의 실행 파일만 배포
# - Playwright 기능 필요 시: pip install playwright && playwright install chromium
# - 예상 크기: 약 50-80MB (UPX 적용 시)
# ============================================================================
