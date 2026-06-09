# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Oyster CCTV System.

Build command:
    pyinstaller oyster.spec

Output: dist/oyster.exe (Windows)
"""

import sys
import os

block_cipher = None

# ── Collect data files ──────────────────────────────────────────────────────
datas = [
    # Templates
    ('app/templates', 'app/templates'),
    # Static files (CSS, JS)
    ('app/static', 'app/static'),
    # Placeholder directories (will be created at runtime if missing)
]

# ── Hidden imports required by face_recognition / dlib / flask ──────────────
hiddenimports = [
    'face_recognition',
    'face_recognition_models',
    'dlib',
    'cv2',
    'flask_sqlalchemy',
    'sqlalchemy',
    'sqlalchemy.dialects.sqlite',
    'PIL',
    'imutils',
    'engineio.async_drivers.threading',
]

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
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
    name='oyster',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,          # set to False for windowed (no console) mode
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,             # add 'app/static/favicon.ico' if you have one
)
