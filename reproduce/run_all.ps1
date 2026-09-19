# Reproduce all automated analyses for the SWE-bench Verified secondary study.
# Requires: Python 3.12, uv (or pip)
# Usage: .\run_all.ps1 [-SkipResultVerification]

param(
    [switch]$SkipResultVerification
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir
$UvCommand = Get-Command uv -ErrorAction SilentlyContinue
if (-not $UvCommand) {
    Write-Host "[ERROR] uv is not installed or is not on PATH." -ForegroundColor Red
    Write-Host "  Run the one-time setup command: .\setup.ps1"
    exit 1
}
$UvExe = $UvCommand.Source
if (-not $env:UV_CACHE_DIR) {
    $env:UV_CACHE_DIR = Join-Path ([System.IO.Path]::GetTempPath()) "gold-signal-uv-cache"
}
New-Item -ItemType Directory -Force -Path $env:UV_CACHE_DIR | Out-Null

function Invoke-Step {
    param([string]$Name, [string]$Script)
    Write-Host "Step: $Name ..."
    & $UvExe run python $Script
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAIL] $Name exited with code $LASTEXITCODE" -ForegroundColor Red
        exit $LASTEXITCODE
    }
    Write-Host "  -> OK" -ForegroundColor Green
    Write-Host ""
}

$TotalSteps = 11

Write-Host "============================================"
Write-Host " SWE-bench Verified Developer-Test Failure Study"
Write-Host "============================================"
Write-Host ""

if (-not (Test-Path "external/PatchDiff/results")) {
    Write-Host "[ERROR] Official PatchDiff archive not found." -ForegroundColor Red
    Write-Host "  Run the resumable one-time setup command: .\setup.ps1"
    exit 1
}

New-Item -ItemType Directory -Force -Path output | Out-Null

Write-Host "Preflight: verify pinned PatchDiff v3 inputs ..."
& $UvExe run python scripts/verify_inputs.py
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
Write-Host "  -> OK" -ForegroundColor Green
Write-Host ""

Invoke-Step -Name "1/$TotalSteps Build developer-test three-state cohort"             -Script scripts/build_analysis_dataset.py
Invoke-Step -Name "2/$TotalSteps Audit upstream label provenance"                    -Script scripts/audit_upstream_labels.py
Invoke-Step -Name "3/$TotalSteps RQ1/RQ3 - Volume models and repository transport"    -Script scripts/run_mixed_effects.py
Invoke-Step -Name "4/$TotalSteps RQ3 - Static final-diff learning baseline"           -Script scripts/run_static_diff_baseline.py
Invoke-Step -Name "5/$TotalSteps RQ2 - Structural alignment and robustness"           -Script scripts/run_structural_alignment.py
Invoke-Step -Name "6/$TotalSteps RQ2 - Within-issue structural sensitivity"           -Script scripts/run_within_issue_sensitivity.py
Invoke-Step -Name "7/$TotalSteps RQ2 - Quantify within-issue design sensitivity"       -Script scripts/run_paired_sensitivity.py
Invoke-Step -Name "8/$TotalSteps RQ4 - Cross-configuration comparison"                -Script scripts/run_rq3_kruskal.py
Invoke-Step -Name "9/$TotalSteps Build repository-transport figure"                   -Script scripts/fig2_repository_transport.py
Invoke-Step -Name "10/$TotalSteps Build exploratory tail figure"                      -Script scripts/fig2_volume_distribution.py
Invoke-Step -Name "11/$TotalSteps Materialize motivating example"                     -Script scripts/deep_dive_24443.py
if ((Test-Path "EXPECTED_RESULTS.json") -and -not $SkipResultVerification) {
    Write-Host "Postflight: verify generated results against the release manifest ..."
    & $UvExe run python scripts/verify_results.py
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
    Write-Host "  -> OK" -ForegroundColor Green
    Write-Host ""
} elseif ($SkipResultVerification) {
    Write-Host "Postflight result verification skipped by explicit maintainer request." -ForegroundColor Yellow
    Write-Host "Refresh EXPECTED_RESULTS.json before publishing this code revision." -ForegroundColor Yellow
    Write-Host ""
}

Write-Host "============================================"
Write-Host " All analysis steps passed. Results are in reproduce/output/"
Write-Host "============================================"
