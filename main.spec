# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path


# Determine project root from PyInstaller-provided SPEC variable when available.
# When PyInstaller executes a spec file it defines `SPEC` with the spec path.
spec_var = globals().get('SPEC')
if spec_var:
    project_root = Path(spec_var).resolve().parent
else:
    project_root = Path.cwd()

icons_dir = project_root / 'resources' / 'icons'
_win_icon = icons_dir / 'logo.ico'
_mac_icon = icons_dir / 'logo.icns'
windows_icon_path = str(_win_icon) if _win_icon.exists() else None
macos_icon_path = str(_mac_icon) if _mac_icon.exists() else None


a = Analysis(
    ['main.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        ('resources', 'resources'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='RuleDone',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=windows_icon_path,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='RuleDone',
)

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='RuleDone.app',
        icon=macos_icon_path,
        bundle_identifier='com.chuqianjing.ruledone',
        info_plist={
            'CFBundleDisplayName': '入档',
            'CFBundleName': '入档',
            'NSPrincipalClass': 'NSApplication',
            'NSHighResolutionCapable': True,
            'NSHumanReadableCopyright': 'Copyright (c) 2026 楚乾靖',
        },
    )
