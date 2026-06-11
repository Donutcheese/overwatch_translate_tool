# 快速激活 venv（在 PowerShell 中 source 式使用）
# 用法: . .\scripts\activate_venv.ps1

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$ActivateScript = Join-Path $ProjectRoot "venv\Scripts\Activate.ps1"

if (-not (Test-Path $ActivateScript)) {
    Write-Host "错误: 未找到 venv。请先运行 .\scripts\setup_venv.ps1" -ForegroundColor Red
    return
}

. $ActivateScript
Write-Host "已激活 venv: $ProjectRoot\venv" -ForegroundColor Green
