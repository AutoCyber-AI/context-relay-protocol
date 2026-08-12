# Copyright (c) 2026 Constantinos Vidiniotis. All rights reserved.
# CRP v5 demo launcher — starts the protocol demo against a local LM Studio model.
#
# Usage (from repo root or this folder):
#     pwsh examples/crp_demos/v4/run_demo.ps1
#     pwsh examples/crp_demos/v4/run_demo.ps1 -LmUrl "http://192.168.0.6:1234/v1" -Port 8774
#
# Then open http://127.0.0.1:<Port>/ and record.

param(
    [string]$LmUrl = "http://192.168.0.6:1234/v1",
    [int]$Port = 8774
)

$ErrorActionPreference = "Stop"

# Resolve repo root (three levels up from this script: v4 -> crp_demos -> examples -> root).
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
Set-Location $RepoRoot

# Prefer the project venv if present.
$Py = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { $Py = "python" }

Write-Host "CRP v5 demo" -ForegroundColor Cyan
Write-Host "  repo : $RepoRoot"
Write-Host "  llm  : $LmUrl"
Write-Host "  url  : http://127.0.0.1:$Port/"
Write-Host ""

# 1) Confirm the LM Studio endpoint is reachable and a model is loaded.
try {
    $models = Invoke-RestMethod -Uri "$LmUrl/models" -TimeoutSec 8
    $loaded = $models.data | Where-Object { $_.id }
    Write-Host ("  models reachable: {0} listed" -f $loaded.Count) -ForegroundColor Green
} catch {
    Write-Host "  WARNING: cannot reach $LmUrl — start LM Studio and load a chat model first." -ForegroundColor Yellow
}

# 2) Start the demo server (foreground; Ctrl+C to stop).
$env:LM_STUDIO_BASE_URL = $LmUrl
$env:CRP_DEMO_PORT = "$Port"
Write-Host "`nStarting demo server (Ctrl+C to stop)…" -ForegroundColor Cyan
& $Py -m examples.crp_demos.v4.server
