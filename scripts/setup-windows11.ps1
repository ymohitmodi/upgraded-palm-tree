# ════════════════════════════════════════════════════════════════════════════
# NYX — Windows 11 Mini-PC one-shot installer
# Run in an elevated PowerShell:
#   Set-ExecutionPolicy -Scope Process Bypass -Force
#   ./scripts/setup-windows11.ps1
# ════════════════════════════════════════════════════════════════════════════
[CmdletBinding()]
param(
    [switch]$InstallOllamaApp,   # also install the local Ollama desktop app
    [switch]$RegisterService     # register NYX to start at boot (lights-out)
)

$ErrorActionPreference = "Stop"
Write-Host "=== NYX Dark Factory — Windows 11 setup ===" -ForegroundColor Cyan

function Test-Command($name) { return [bool](Get-Command $name -ErrorAction SilentlyContinue) }

# 1. Prerequisites via winget --------------------------------------------------
if (-not (Test-Command winget)) {
    throw "winget not found. Install 'App Installer' from the Microsoft Store, then re-run."
}
if (-not (Test-Command git)) {
    Write-Host "Installing Git..." -ForegroundColor Yellow
    winget install --id Git.Git -e --accept-source-agreements --accept-package-agreements
}
if (-not (Test-Command py)) {
    Write-Host "Installing Python 3.11..." -ForegroundColor Yellow
    winget install --id Python.Python.3.11 -e --accept-source-agreements --accept-package-agreements
}

# 2. Optional local Ollama (for offline fallback models) -----------------------
if ($InstallOllamaApp) {
    Write-Host "Installing Ollama desktop app..." -ForegroundColor Yellow
    winget install --id Ollama.Ollama -e --accept-source-agreements --accept-package-agreements
}

# 3. Virtual environment + install --------------------------------------------
Write-Host "Creating virtual environment (.venv)..." -ForegroundColor Yellow
py -3.11 -m venv .venv
& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
# investing extra bundles edgartools (live SEC/XBRL) + pypdf (read PDF letters).
python -m pip install -e ".[http,yaml,investing]"

# 4. Configuration -------------------------------------------------------------
if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
    Write-Host "Created .env from template." -ForegroundColor Green
    $key = Read-Host "Paste your OLLAMA_API_KEY (leave blank to stay in MOCK mode)"
    if ($key) {
        (Get-Content .env) -replace '^OLLAMA_API_KEY=.*', "OLLAMA_API_KEY=$key" | Set-Content .env
        Write-Host "OLLAMA_API_KEY saved to .env" -ForegroundColor Green
    }
}

# 5. Smoke test ----------------------------------------------------------------
Write-Host "`nRunning 'nyx doctor'..." -ForegroundColor Cyan
nyx doctor

# 6. Optional boot service -----------------------------------------------------
if ($RegisterService) {
    Write-Host "Registering NYX as a scheduled task at startup..." -ForegroundColor Yellow
    $cwd = (Get-Location).Path
    $action  = New-ScheduledTaskAction -Execute "powershell.exe" `
        -Argument "-WindowStyle Hidden -Command `"cd '$cwd'; .\.venv\Scripts\Activate.ps1; nyx serve`""
    $trigger = New-ScheduledTaskTrigger -AtStartup
    Register-ScheduledTask -TaskName "NYX Dark Factory" -Action $action -Trigger $trigger `
        -RunLevel Highest -Force
    Write-Host "Registered 'NYX Dark Factory' scheduled task." -ForegroundColor Green
}

Write-Host "`n=== Setup complete ===" -ForegroundColor Cyan
Write-Host "Try:  nyx build `"Ship a waitlist landing page with email capture`""
