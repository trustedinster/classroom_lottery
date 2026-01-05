# -*- coding: utf-8 -*-
# Nuitka 顺序构建脚本 (支持不同图标 + 依赖共享)
# 功能：依次构建 main.py, daemon.py, launcher.py, update.py，并将所有依赖合并到同一目录

param(
    [switch]$Clean = $false
)

# ==================== 环境检查 ====================
$ErrorActionPreference = "Stop"
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Nuitka 多程序构建脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 检查 Python 是否安装
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "未找到 Python，请确保已将 Python 添加到 PATH 环境变量中。"
    exit 1
}

# ==================== 路径与全局配置 ====================
$ScriptPath = $PSScriptRoot
$AssetsPath = Join-Path $ScriptPath "assets"
# 最终输出目录 (所有exe和依赖将合并于此)
$FinalDistDir = Join-Path $ScriptPath "dist\classroom_lottery"

# 读取版本号的辅助函数
function Get-VersionContent {
    param($FilePath)
    if (Test-Path $FilePath) {
        $Content = Get-Content $FilePath -TotalCount 1
        if ($Content -match "^\d+\.\d+\.\d+\.\d+$") {
            return $Content
        }
    }
    return $null
}

# 默认版本号和图标路径
$DefaultVersion = Get-VersionContent (Join-Path $ScriptPath "version_info.txt")
$DefaultIcon = Join-Path $AssetsPath "icon.ico"
if (-not (Test-Path $DefaultIcon)) { $DefaultIcon = $null }

# ==================== 应用程序配置列表 ====================
# 定义每个程序的构建参数：图标、版本、是否需要控制台、包含/排除的库
$Apps = @(
    @{
        Name       = "课堂抽号程序"
        Script     = "main.py"
        Icon       = "assets\icon.ico"
        VerFile    = "version_info.txt"
        Console    = $false
        Plugin     = "pyside2"
        Includes   = @("pyttsx3", "pyttsx3.drivers", "keyboard", "PIL", "psutil")
        Excludes   = @("matplotlib", "notebook", "jupyter", "IPython", "pytest", "sphinx", "pandas")
    },
    @{
        Name       = "daemon"
        Script     = "daemon.py"
        Icon       = "assets\daemon.ico"
        VerFile    = "version_info_daemon.txt"
        Console    = $false
        Plugin     = "" # 守护进程不需要 GUI 插件
        Includes   = @("psutil")
        Excludes   = @("PySide2", "PIL", "pyttsx3", "winsound", "keyboard", "matplotlib", "notebook", "jupyter", "IPython", "pandas")
    },
    @{
        Name       = "启动器"
        Script     = "launcher.py"
        Icon       = "assets\launcher.ico"
        VerFile    = "version_info_launcher.txt"
        Console    = $false
        Plugin     = "pyside2"
        Includes   = @("psutil", "openpyxl")
        Excludes   = @("matplotlib", "pyttsx3", "winsound", "keyboard", "pandas", "notebook", "jupyter", "IPython")
    },
    @{
        Name       = "update"
        Script     = "update.py"
        Icon       = "assets\update.ico"
        VerFile    = "version_info_update.txt"
        Console    = $false  # <--- 已修改为 false，update程序本身有GUI，不需要控制台
        Plugin     = "pyside2" # update.py 引用了 PySide2
        Includes   = @("requests", "tqdm", "psutil")
        Excludes   = @("matplotlib", "pyttsx3", "winsound", "keyboard", "PIL", "pandas", "notebook", "jupyter", "IPython")
    }
)

# ==================== 准备构建 ====================
# 清理旧的构建目录
if (Test-Path $FinalDistDir) {
    Write-Host "清理旧输出目录: $FinalDistDir" -ForegroundColor Gray
    Remove-Item $FinalDistDir -Recurse -Force
}
New-Item -ItemType Directory -Path $FinalDistDir | Out-Null

# ==================== 执行循环构建 ====================
foreach ($App in $Apps) {
    Write-Host "----------------------------------------" -ForegroundColor Cyan
    Write-Host "正在构建: $($App.Name)" -ForegroundColor Yellow

    # 1. 处理图标路径 (回退逻辑)
    $AppIconPath = Join-Path $ScriptPath $App.Icon
    if (-not (Test-Path $AppIconPath)) {
        Write-Warning "未找到特定图标 '$($App.Icon)'，尝试使用默认图标。"
        $AppIconPath = $DefaultIcon
    }

    # 2. 处理版本信息 (回退逻辑)
    $AppVersion = Get-VersionContent (Join-Path $ScriptPath $App.VerFile)
    if (-not $AppVersion) {
        $AppVersion = $DefaultVersion
        if ($AppVersion) {
            Write-Host "使用默认版本号: $AppVersion" -ForegroundColor Gray
        }
    }

    # 3. 构建 Nuitka 参数
    $NuitkaArgs = @(
        "--standalone"
        "--output-dir=$FinalDistDir"
        "--remove-output" # 删除构建缓存，保留产物
        "--assume-yes-for-downloads"
        "--lto=yes"        # 链接时优化，减小体积

        # 窗口/控制台设置
        "--windows-console-mode=$(if($App.Console){'force'}else{'disable'})"
    )

    # 插件设置
    if ($App.Plugin) {
        $NuitkaArgs += "--enable-plugin=$($App.Plugin)"
    }

    # 包含包
    foreach ($Inc in $App.Includes) {
        $NuitkaArgs += "--include-package=$Inc"
    }

    # 排除包
    foreach ($Exc in $App.Excludes) {
        $NuitkaArgs += "--nofollow-import-to=$Exc"
    }

    # 资源文件
    # 注意：multidist/standalone模式下，资源会被放入exe同级目录或子目录
    # 我们统一处理：将 assets 指向最终输出目录
    $AssetsSource = Join-Path $ScriptPath "assets"
    if (Test-Path $AssetsSource) {
        # Nuitka 会将数据文件放入 dist 内的 assets 文件夹
        $NuitkaArgs += "--include-data-dir=$AssetsSource=assets"
    }

    # 图标参数
    if ($AppIconPath) {
        $NuitkaArgs += "--windows-icon-from-ico=$AppIconPath"
    }

    # 版本参数
    if ($AppVersion) {
        $NuitkaArgs += "--windows-file-version=$AppVersion"
        $NuitkaArgs += "--windows-product-version=$AppVersion"
    }

    # 指定要编译的脚本
    $ScriptPathFull = Join-Path $ScriptPath $App.Script
    $NuitkaArgs += $ScriptPathFull

    # 4. 执行构建
    # python -m nuitka ...
    Write-Host "执行命令: python -m nuitka $($App.Name) ..." -ForegroundColor DarkGray
    & python -m nuitka @NuitkaArgs

    if ($LASTEXITCODE -ne 0) {
        Write-Error "构建 $($App.Name) 失败！错误代码: $LASTEXITCODE"
        exit $LASTEXITCODE
    }
}

# ==================== 构建后处理：扁平化目录 ====================
Write-Host "----------------------------------------" -ForegroundColor Cyan
Write-Host "正在合并依赖和文件..." -ForegroundColor Yellow

# Nuitka 会在输出目录下生成 <ScriptName>.dist 文件夹，我们需要把内容提取出来
$SubDistDirs = Get-ChildItem -Path $FinalDistDir -Directory -Filter "*.dist"

foreach ($SubDir in $SubDistDirs) {
    Write-Host "处理目录: $($SubDir.Name)" -ForegroundColor Gray

    # 1. 移动所有 .exe 到根目录
    $Exes = Get-ChildItem -Path $SubDir.FullName -Filter "*.exe"
    foreach ($Exe in $Exes) {
        $DestPath = Join-Path $FinalDistDir $Exe.Name
        # 如果已存在则覆盖
        Move-Item -Path $Exe.FullName -Destination $DestPath -Force
    }

    # 2. 移动所有依赖库 到根目录
    # Nuitka 生成的依赖主要在 .dist 根目录下
    $Deps = Get-ChildItem -Path $SubDir.FullName -File | Where-Object { $_.Extension -in @('.dll', '.pyd', '.so', '.zip') }
    foreach ($Dep in $Deps) {
        $DestPath = Join-Path $FinalDistDir $Dep.Name
        # 如果文件已存在，通常不需要覆盖，除非版本不同。这里为了简单强制覆盖
        Move-Item -Path $Dep.FullName -Destination $DestPath -Force
    }

    # 3. 移动其他文件夹 (如 lib) 到根目录
    $LibDirs = Get-ChildItem -Path $SubDir.FullName -Directory | Where-Object { $_.Name -eq "lib" }
    foreach ($LibDir in $LibDirs) {
        $DestPath = Join-Path $FinalDistDir $LibDir.Name
        # 简单粗暴合并：如果存在则报错或手动处理，这里假设Nuitka生成的依赖库路径一致且结构简单
        # 更稳健的做法是遍历内部文件并移动，但通常合并整个文件夹即可
        if (-not (Test-Path $DestPath)) {
            Move-Item -Path $LibDir.FullName -Destination $DestPath -Force
        } else {
            # 如果 lib 文件夹已存在，合并里面的内容
            Write-Host "  合并 lib 文件夹内容..." -ForegroundColor DarkGray
            Get-ChildItem -Path $LibDir.FullName -Recurse | ForEach-Object {
                $TargetPath = Join-Path $FinalDistDir "lib\$($_.Name)"
                $RelativePath = $_.FullName.Substring($LibDir.Parent.FullName.Length + 1)
                $FinalTargetPath = Join-Path $FinalDistDir $RelativePath

                # 创建目标目录结构
                $TargetDir = Split-Path -Parent $FinalTargetPath
                if (-not (Test-Path $TargetDir)) {
                    New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
                }

                Copy-Item -Path $_.FullName -Destination $FinalTargetPath -Force
            }
        }
    }
}

# 清理空子文件夹
$SubDistDirs | Remove-Item -Recurse -Force

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "构建完成！" -ForegroundColor Green
Write-Host "最终产物位置: $FinalDistDir" -ForegroundColor Cyan

# 列出生成的文件
Write-Host "生成文件列表:" -ForegroundColor Gray
Get-ChildItem -Path $FinalDistDir -Filter "*.exe" | ForEach-Object {
    $SizeMB = [math]::Round($_.Length / 1MB, 2)
    Write-Host "  - $($_.Name) ($SizeMB MB)" -ForegroundColor White
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "按任意键退出..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
