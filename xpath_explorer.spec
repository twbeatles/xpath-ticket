# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['251214 xpath 조사기(모든 티켓 사이트).py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'xpath_constants',
        'xpath_styles',
        'xpath_config',
        'xpath_widgets',
        'xpath_browser',
        'xpath_workers',
        'PyQt6',
        'selenium',
        'undetected_chromedriver'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='XPathExplorer_v3.2',
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
    icon=None
)
