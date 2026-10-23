# PowerShell 一键自动化测试与打包部署脚本 (scripts/build_exe.ps1)
$ErrorActionPreference = "Stop"
Set-Location -Path (Split-Path -Parent $PSScriptRoot)

Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host "  特码智能收单与风控系统 Pro - 自动化测试与打包服务  " -ForegroundColor Cyan
Write-Host "=====================================================" -ForegroundColor Cyan

python scripts/build_exe.py
if ($LASTEXITCODE -ne 0) {
    Write-Error "构建流水线执行失败！"
    exit $LASTEXITCODE
}
