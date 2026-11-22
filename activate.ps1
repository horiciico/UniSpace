# UniSpace Virtual Environment Activation Shortcut
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$activatePath = Join-Path $scriptDir ".venv\Scripts\Activate.ps1"

if (-not (Test-Path $activatePath)) {
    Write-Error "Virtual environment not found at $activatePath. Did you create .venv?"
    return
}

# Run the activation script in the caller's scope
. $activatePath
Write-Host "UniSpace virtual environment (.venv) activated." -ForegroundColor Green

