# -*- coding: utf-8 -*-
# Nuitka Multidist 构建脚本
# 功能：将 main.py, daemon.py, launcher.py, update.py 打包到同一目录并共享依赖

param(
    [switch]$Clean = $false
)

# ==================== 环境检查 ====================
$ErrorActionPreference = "Stop"
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Nuitka Multidist 构建脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 检查 Python 是否安装
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "未找到 Python，请确保已将 Python 添加到 PATH 环境变量中。"
    exit 1
}

# ==================== 路径与图标配置 ====================
$ScriptPath = $PSScriptRoot
$AssetsPath = Join-Path $ScriptPath "assets"

# 1. 主程序图标 (默认图标)
$MainIconPath = Join-Path $AssetsPath "icon.ico"
if (-not (Test-Path $MainIconPath)) {
    Write-Warning "未找到 assets\icon.ico，将使用默认图标。"
    $MainIconPath = $null
}

# 注意：Nuitka 的 multidist 模式下，所有 EXE 默认共用一个图标。
# 如果必须为每个 EXE 设置不同图标，需要在构建后使用工具（如 ResourceHacker）手动修改，
# 或者放弃 multidist 分开构建。这里为了实现依赖共享，统一使用主图标。
$GlobalIcon = $MainIconPath

# 2. 版本信息
# Nuitka 需要具体的版本号字符串，而非 PyInstaller 的 .txt 文件
# 如果 version_info.txt 存在且包含版本号（如 1.0.0.0），可在此解析，否则留空
$VersionInfo = ""
$VersionFilePath = Join-Path $ScriptPath "version_info.txt"
if (Test-Path $VersionFilePath) {
    # 简单尝试读取第一行作为版本号，如果格式不对请手动修改下面的变量
    $Content = Get-Content $VersionFilePath -TotalCount 1
    if ($Content -match "^\d+\.\d+\.\d+\.\d+$") {
        $VersionInfo = $Content
        Write-Host "检测到版本号: $VersionInfo" -ForegroundColor Green
    } else {
        Write-Warning "version_info.txt 格式不为纯版本号 (如 1.0.0.0)，将跳过版本信息设置。"
    }
}

# ==================== 构建参数 ====================
$DistDir = Join-Path $ScriptPath "dist\classroom_lottery"

# Nuitka 基础参数
$NuitkaArgs = @(
    "--standalone"
    # 启用 multidist：指定多个 main 入口
    "--main=main.py"
    "--main=daemon.py"
    "--main=launcher.py"
    "--main=update.py"

    # 输出配置
    "--output-dir=$DistDir"

    # 所有程序都是 UI 框架，统一关闭控制台
    "--windows-console-mode=disable"

    # 启用 PySide2 插件（GUI 程序必需）
    "--enable-plugin=pyside2"

    # 清理构建缓存，减小体积
    "--remove-output"

    # 优化选项
    "--assume-yes-for-downloads"
    "--lto=no" # 关闭 LTO 可以加快编译速度，如果追求极致体积可改为 yes

    # 依赖排除 (基于原 spec 的 excludes，但要保留被使用的)
    # 注意：update.py 使用了 tqdm，main.py 可能需要 PIL/keyboard
    # 所以原 spec 中的 excludes 需要调整，排除不常用的大库即可
    "--nofollow-import-to=matplotlib"
    "--nofollow-import-to=notebook"
    "--nofollow-import-to=jupyter"
    "--nofollow-import-to=IPython"
    "--nofollow-import-to=pytest"
    "--nofollow-import-to=sphinx"

    # 隐藏导入 / 显式包含 (包含所有程序可能用到的模块)
    "--include-package=pyttsx3"
    "--include-package=pyttsx3.drivers"
    "--include-package=keyboard"
    "--include-package=PIL"
    "--include-package=psutil"
    "--include-package=pandas"
    "--include-package=openpyxl"
    "--include-package=requests"
    "--include-package=tqdm"

    # 数据文件包含
    # 注意：multidist 下，数据文件会统一放到 dist 根目录的 assets 文件夹中
    "--include-data-dir=assets=assets"
)

# 如果存在图标，添加图标参数
if ($GlobalIcon) {
    $NuitkaArgs += "--windows-icon-from-ico=$GlobalIcon"
}

# 如果存在版本号，添加版本参数
if ($VersionInfo) {
    $FileVersion, $ProductVersion = $VersionInfo, $VersionInfo
    $NuitkaArgs += "--windows-file-version=$FileVersion"
    $NuitkaArgs += "--windows-product-version=$ProductVersion"
}

# ==================== 执行构建 ====================
Write-Host "开始执行 Nuitka 构建..." -ForegroundColor Yellow
Write-Host "输出目录: $DistDir" -ForegroundColor Gray

# 组合完整命令
# 使用 & 调用 python，并将参数数组展开
& python -m nuitka @NuitkaArgs

# 【修复处】将 -neq 改为 -ne
if ($LASTEXITCODE -ne 0) {
    Write-Error "构建失败！错误代码: $LASTEXITCODE"
    exit $LASTEXITCODE
}

# ==================== 构建后处理 ====================
Write-Host "----------------------------------------" -ForegroundColor Cyan
Write-Host "构建成功！" -ForegroundColor Green

# 查找实际的输出目录 (Nuitka 会根据第一个 main 文件名创建 .dist 目录)
# 假设 main.py 是第一个，输出目录通常是 dist/classroom_lottery/main.dist
# 但由于我们指定了 --output-dir=dist/classroom_lottery，Nuktia 的行为是在该目录下创建 <Name>.dist
# 实际上，在 multidist 模式下，多个 EXE 都在同一个 .dist 目录里。

$ActualDistDir = Get-ChildItem -Path $DistDir -Directory -Filter "*.dist" | Select-Object -First 1

if ($ActualDistDir) {
    Write-Host "最终产物位置: $($ActualDistDir.FullName)" -ForegroundColor Cyan
    Write-Host "包含以下文件:" -ForegroundColor Gray
    Get-ChildItem -Path $ActualDistDir.FullName -Filter "*.exe" | ForEach-Object {
        Write-Host "  - $($_.Name)" -ForegroundColor White
    }
} else {
    Write-Warning "未能在 $DistDir 下找到 .dist 输出目录，请检查构建日志。"
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "按任意键退出..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
