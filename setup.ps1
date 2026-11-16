$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath 'backend\.venv\Scripts\python.exe')) { py -m venv backend\.venv }
& 'backend\.venv\Scripts\python.exe' -m pip install -r backend\requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
npm.cmd install
if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
