# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from PyInstaller.utils.hooks import collect_submodules

# ==================== 基础配置 ====================
block_cipher = None
icon_path = 'assets/icon.ico'
version_info_path = 'version_info.txt'

# 检测图标文件是否存在
if not os.path.exists(icon_path):
    icon_path = None
    print("警告：未找到自定义图标文件，将使用默认图标")

# 检测版本信息文件是否存在
if not os.path.exists(version_info_path):
    version_info_path = None
    print("警告：未找到版本信息文件，将使用默认版本信息")

# ==================== 主程序分析 (main.py) ====================
a_main = Analysis(
    ['main.py'],
    pathex=[os.getcwd()],
    binaries=[],
    datas=[
        ('assets/icon.ico', 'assets'),
        ('assets/rise_enable.wav', 'assets'),
        ('config.ini', '.'),
        ('students.json', '.') if os.path.exists('students.json') else None,
    ],
    hiddenimports=[
        'PySide2.QtCore',
        'PySide2.QtGui',
        'PySide2.QtWidgets',
        'pyttsx3.drivers',
        'pyttsx3.drivers.dummy',
        'pyttsx3.drivers.espeak',
        'pyttsx3.drivers.nsss',
        'pyttsx3.drivers.sapi5',
        'winsound',
        'keyboard',
        'configparser',
        'json',
        'pickle',
        'threading',
        'random',
        'datetime',
        'logging',
        'psutil',
        'tempfile',
        'shutil',
        'argparse',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'pyexpat',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'notebook',
        'jupyter',
        'IPython',
        'pytest',
        'sphinx',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# ==================== 守护进程分析 (daemon.py) ====================
a_daemon = Analysis(
    ['daemon.py'],
    pathex=[os.getcwd()],
    binaries=[],
    datas=[],
    hiddenimports=[
        'subprocess',
        'logging',
        'argparse',
        'datetime',
        'time',
        'os',
        'sys',
        'psutil',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PIL',
        'PySide2',
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'pyttsx3',
        'winsound',
        'keyboard',
        'configparser',
        'json',
        'pickle',
        'random',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# ==================== 启动器分析 (launcher.py) ====================
a_launcher = Analysis(
    ['launcher.py'],
    pathex=[os.getcwd()],
    binaries=[],
    datas=[
        ('config.ini', '.'),
        ('assets/*', 'assets'),
    ],
    hiddenimports=[
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'configparser',
        'subprocess',
        'psutil',
        'pandas',
        'openpyxl',
        'json',
        'glob',
        'threading',
        'time',
        'os',
        'pathlib',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'scipy',
        'notebook',
        'jupyter',
        'IPython',
        'PySide2',
        'pyttsx3',
        'winsound',
        'keyboard',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# ==================== 主程序可执行文件 ====================
pyz_main = PYZ(
    a_main.pure,
    a_main.zipped_data,
    cipher=block_cipher,
)

exe_main = EXE(
    pyz_main,
    a_main.scripts,
    [],
    name='课堂抽号程序',
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
    icon=icon_path,
    version=version_info_path,
    onefile=False,  # 目录模式
)

# ==================== 守护进程可执行文件 ====================
pyz_daemon = PYZ(
    a_daemon.pure,
    a_daemon.zipped_data,
    cipher=block_cipher,
)

exe_daemon = EXE(
    pyz_daemon,
    a_daemon.scripts,
    [],
    name='daemon',
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
    icon=icon_path,
    version=version_info_path,
    onefile=False,  # 目录模式
)

# ==================== 启动器可执行文件 ====================
pyz_launcher = PYZ(
    a_launcher.pure,
    a_launcher.zipped_data,
    cipher=block_cipher,
)

exe_launcher = EXE(
    pyz_launcher,
    a_launcher.scripts,
    [],
    name='launcher',
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
    icon=icon_path,
    version=version_info_path,
    onefile=False,  # 目录模式
)

# ==================== 多包收集 ====================
coll_main = COLLECT(
    exe_main,
    a_main.binaries,
    a_main.zipfiles,
    a_main.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='课堂抽号程序',
    distpath='dist',
)

coll_daemon = COLLECT(
    exe_daemon,
    a_daemon.binaries,
    a_daemon.zipfiles,
    a_daemon.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='daemon',
    distpath='dist',
)

coll_launcher = COLLECT(
    exe_launcher,
    a_launcher.binaries,
    a_launcher.zipfiles,
    a_launcher.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='launcher',
    distpath='dist',
)
