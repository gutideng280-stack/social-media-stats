# Social Media Stats Tool Launcher
$host.ui.RawUI.WindowTitle = "Social Media Stats Tool"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $scriptDir "backend"

Set-Location $backendDir

# Check Python
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "[ERROR] Python not found. Please install Python and add it to PATH." -ForegroundColor Red
    pause
    exit 1
}

# Install dependencies
Write-Host "[1/2] Checking dependencies..." -ForegroundColor Cyan
python -m pip install -q -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARN] Dependency install may have issues, trying to continue..." -ForegroundColor Yellow
}

# Start service
Write-Host "[2/2] Starting backend server..." -ForegroundColor Cyan
Write-Host ""
Write-Host "Please wait, then open your browser at:" -ForegroundColor Green
Write-Host "  http://localhost:5003" -ForegroundColor Green
Write-Host ""

python app.py

pause
