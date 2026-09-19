# One-time Windows setup: install uv if needed, then fetch pinned PatchDiff data.

param(
    [switch]$Force,
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir
if (-not $env:UV_CACHE_DIR) {
    $env:UV_CACHE_DIR = Join-Path ([System.IO.Path]::GetTempPath()) "gold-signal-uv-cache"
}
New-Item -ItemType Directory -Force -Path $env:UV_CACHE_DIR | Out-Null

$UvCommand = Get-Command uv -ErrorAction SilentlyContinue
$UvExe = if ($UvCommand) { $UvCommand.Source } else { $null }
if (-not $UvExe) {
    Write-Host "uv was not found. Installing it from the official Astral installer..."
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    foreach ($Candidate in @(
        (Join-Path $HOME ".local\bin\uv.exe"),
        (Join-Path $HOME ".cargo\bin\uv.exe")
    )) {
        if (Test-Path $Candidate) {
            $UvExe = $Candidate
            break
        }
    }
}

if (-not $UvExe) {
    throw "uv installation finished but uv.exe was not found. Reopen PowerShell and rerun .\setup.ps1."
}

$SetupArgs = @("run", "scripts/setup_external_data.py")
if ($Force) {
    $SetupArgs += "--force"
}
if ($CheckOnly) {
    $SetupArgs += "--check-only"
}
& $UvExe @SetupArgs
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "Setup complete. Run .\run_all.ps1 to reproduce all results." -ForegroundColor Green
