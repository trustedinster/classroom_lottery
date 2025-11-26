# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from PyInstaller.utils.hooks import collect_submodules

# 基础配置
block_cipher = None
script_path = 'main.py'
icon_path = 'assets/icon.ico'  # 可替换为自定义图标（无则自动使用默认）

# 检测图标文件是否存在
if not os.path.exists(icon_path):
    icon_path = None
    print("警告：未找到自定义图标文件，将使用默认图标")

a = Analysis(
    [script_path],
    pathex=[os.getcwd()],
    binaries=[],
    datas=[('assets/icon.ico', 'assets'), ('assets/rise_enable.wav', 'assets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher,
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='课堂抽号程序',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 隐藏控制台
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,  # 绑定图标
    onefile=False,  # 生成单文件EXE
)

# 输出目录配置
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='课堂抽号程序',
    distpath='dist',  # 输出到dist目录
)