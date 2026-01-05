# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from PyInstaller.utils.hooks import collect_submodules

# ==================== 基础配置 ====================
block_cipher = None

# 主程序图标和版本信息
main_icon_path = 'assets/icon.ico'
main_version_info_path = 'version_info.txt'

# 守护进程图标和版本信息
daemon_icon_path = 'assets/daemon.ico'
daemon_version_info_path = 'version_info_daemon.txt'

# 启动器图标和版本信息
launcher_icon_path = 'assets/launcher.ico'
launcher_version_info_path = 'version_info_launcher.txt'

# 更新程序图标和版本信息
update_icon_path = 'assets/update.ico'
update_version_info_path = 'version_info_update.txt'

# 检测主程序图标文件是否存在
if not os.path.exists(main_icon_path):
    main_icon_path = 'assets/icon.ico' if os.path.exists('assets/icon.ico') else None
    if not main_icon_path:
        print("警告：未找到主程序图标文件，将使用默认图标")

# 检测守护进程图标文件是否存在
if not os.path.exists(daemon_icon_path):
    daemon_icon_path = 'assets/icon.ico' if os.path.exists('assets/icon.ico') else main_icon_path

# 检测启动器图标文件是否存在
if not os.path.exists(launcher_icon_path):
    launcher_icon_path = 'assets/icon.ico' if os.path.exists('assets/icon.ico') else main_icon_path

# 检测更新程序图标文件是否存在
if not os.path.exists(update_icon_path):
    update_icon_path = 'assets/icon.ico' if os.path.exists('assets/icon.ico') else main_icon_path

# 检测主程序版本信息文件是否存在
if not os.path.exists(main_version_info_path):
    main_version_info_path = None
    print("警告：未找到主程序版本信息文件，将使用默认版本信息")

# 检测守护进程版本信息文件是否存在
if not os.path.exists(daemon_version_info_path):
    daemon_version_info_path = main_version_info_path

# 检测启动器版本信息文件是否存在
if not os.path.exists(launcher_version_info_path):
    launcher_version_info_path = main_version_info_path

# 检测更新程序版本信息文件是否存在
if not os.path.exists(update_version_info_path):
    update_version_info_path = main_version_info_path

# ==================== 主程序分析 (main.py) ====================
a_main = Analysis(
    ['main.py'],
    pathex=[os.getcwd()],
    binaries=[],
    datas=[
        ('assets/icon.ico', 'assets'),
        ('assets/rise_enable.wav', 'assets'),
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
        'tqdm',
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
        'random',
        'tqdm',
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
        ('assets/*', 'assets'),
    ],
    hiddenimports=[
        'PySide2.QtCore',
        'PySide2.QtGui',
        'PySide2.QtWidgets',
        'configparser',
        'subprocess',
        'psutil',
        'openpyxl',
        'json',
        'glob',
        'threading',
        'time',
        'os',
        'pathlib',
        'csv',
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
        'pyttsx3',
        'winsound',
        'keyboard',
        'tqdm',
        'pandas',  # 移除pandas依赖，启动器现在使用openpyxl和csv
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
    icon=main_icon_path,
    version=main_version_info_path,
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
    icon=daemon_icon_path,
    version=daemon_version_info_path,
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
    name='启动器',
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
    icon=launcher_icon_path,
    version=launcher_version_info_path,
    onefile=False,  # 目录模式
)

# ==================== 更新程序分析 (update.py) ====================
a_update = Analysis(
    ['update.py'],
    pathex=[os.getcwd()],
    binaries=[],
    datas=[],
    hiddenimports=[
        'requests',
        'json',
        'typing',
        're',
        'os',
        'logging',
        'zipfile',
        'shutil',
        'argparse',
        'time',
        'datetime',
        'tqdm',
        'psutil',
        'subprocess',
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
        'PySide2',
        'pyttsx3',
        'winsound',
        'keyboard',
        'PIL',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# ==================== 更新程序可执行文件 ====================
pyz_update = PYZ(
    a_update.pure,
    a_update.zipped_data,
    cipher=block_cipher,
)

exe_update = EXE(
    pyz_update,
    a_update.scripts,
    [],
    name='update',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=update_icon_path,
    version=update_version_info_path,
    onefile=False,  # 目录模式
)

# ==================== 共享多包收集 ====================
coll = COLLECT(
    # 1. 放入所有的 EXE
    exe_main,
    exe_daemon,
    exe_launcher,
    exe_update,
    # 2. 放入所有的依赖项 (PyInstaller 会自动去重)
    a_main.binaries,
    a_main.zipfiles,
    a_main.datas,
    a_daemon.binaries,
    a_daemon.zipfiles,
    a_daemon.datas,
    a_launcher.binaries,
    a_launcher.zipfiles,
    a_launcher.datas,
    a_update.binaries,
    a_update.zipfiles,
    a_update.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='classroom_lottery',  # 最终输出目录名称：dist/classroom_lottery
    distpath='dist',
)