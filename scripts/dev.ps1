# REWIND task runner for native Windows (mirrors the Makefile targets).
# Usage: powershell -File scripts/dev.ps1 <setup|dev|backend|frontend|test|lint|contracts|demo|train>
param([Parameter(Mandatory = $true)][string]$Target)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Py = Join-Path $Root "backend\.venv\Scripts\python.exe"

function Invoke-Step([string]$Dir, [string]$Exe, [string[]]$ArgList) {
    Push-Location $Dir
    try {
        & $Exe @ArgList
        if ($LASTEXITCODE -ne 0) { throw "$Exe $($ArgList -join ' ') failed with exit code $LASTEXITCODE" }
    } finally { Pop-Location }
}

switch ($Target) {
    "setup" {
        if (-not (Test-Path $Py)) { python -m venv (Join-Path $Root "backend\.venv") }
        Invoke-Step $Root $Py @("-m", "pip", "install", "--upgrade", "pip")
        Invoke-Step $Root $Py @("-m", "pip", "install", "-e", "backend[dev,perf]")
        Invoke-Step (Join-Path $Root "frontend") "npm" @("install")
    }
    "backend" { Invoke-Step (Join-Path $Root "backend") $Py @("-m", "uvicorn", "rewind.main:app", "--reload", "--port", "8000") }
    "frontend" { Invoke-Step (Join-Path $Root "frontend") "npm" @("run", "dev") }
    "dev" {
        Start-Process -FilePath $Py -ArgumentList "-m", "uvicorn", "rewind.main:app", "--reload", "--port", "8000" -WorkingDirectory (Join-Path $Root "backend")
        Invoke-Step (Join-Path $Root "frontend") "npm" @("run", "dev")
    }
    "test" {
        Invoke-Step (Join-Path $Root "backend") $Py @("-m", "pytest", "-q")
        Invoke-Step (Join-Path $Root "frontend") "npm" @("test")
    }
    "lint" {
        Invoke-Step (Join-Path $Root "backend") $Py @("-m", "ruff", "check", "rewind", "tests", "../scripts")
        Invoke-Step (Join-Path $Root "backend") $Py @("-m", "mypy", "rewind")
        Invoke-Step (Join-Path $Root "frontend") "npm" @("run", "lint")
        Invoke-Step (Join-Path $Root "frontend") "npm" @("run", "typecheck")
    }
    "contracts" { Invoke-Step $Root $Py @("scripts/gen_data_contracts.py") }
    "demo" { Invoke-Step $Root $Py @("scripts/make_demo.py") }
    "train" {
        foreach ($m in "synth_dataset", "train_temporal", "train_xgb", "evaluate") {
            Invoke-Step $Root $Py @("-m", "rewind.training.$m")
        }
    }
    default { throw "Unknown target '$Target'" }
}
