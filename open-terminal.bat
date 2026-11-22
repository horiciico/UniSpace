@echo off
cd /d "%~dp0"
echo Launching PowerShell with UniSpace .venv activated...
powershell -NoExit -ExecutionPolicy Bypass -Command "& { if (Test-Path '.\.venv\Scripts\Activate.ps1') { . '.\.venv\Scripts\Activate.ps1'; Write-Host 'UniSpace (.venv) activated.' -ForegroundColor Green } else { Write-Warning 'Virtual environment not found at .venv' } }"

