$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    & python -m venv (Join-Path $Root ".venv")
    & $Python -m pip install -r (Join-Path $Root "requirements.txt")
}

Set-Location $Root
& $Python -m uvicorn app.main:app --host 127.0.0.1 --port 12306

