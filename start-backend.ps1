$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
& "$PSScriptRoot\backend\.venv\Scripts\python.exe" -m uvicorn app:app --app-dir backend --host 127.0.0.1 --port 8000
