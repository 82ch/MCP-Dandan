# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Collect all submodules from engines and transports
hiddenimports = collect_submodules('engines') + collect_submodules('transports') + collect_submodules('utils')

# Add additional hidden imports
hiddenimports += [
    'aiohttp',
    'aiosqlite',
    'certifi',
    'mistralai',
    'yara',
    'dotenv',
    'aiofiles',
    'requests',
]

# Collect data files
datas = []
datas += collect_data_files('certifi')
datas += [('schema.sql', '.')]

# Add yara rules if they exist
if os.path.exists('yara_rules'):
    datas += [('yara_rules', 'yara_rules')]

# Include all Python source files as data files
datas += [
    ('engines', 'engines'),
    ('transports', 'transports'),
    ('utils', 'utils'),
]

block_cipher = None

a = Analysis(
    ['server.py'],
    pathex=[],
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
    name='82ch-server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Set to True for console application
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon path if you have one: 'front/icons/dandan.ico'
)
