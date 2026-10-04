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
# Use an existing Python 3.10+ if present (e.g. Miniconda); else the winget 3.11.
Write-Host "Creating virtual environment (.venv)..." -ForegroundColor Yellow
$py = if (Get-Command py -ErrorAction SilentlyContinue) { "py -3.11" } else { "python" }
Invoke-Expression "$py -m venv .venv"
& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
# investing = edgartools (SEC/XBRL) + pypdf (PDF letters); http = requests+brotli
# (older Berkshire letters are Brotli-encoded). Everything for a live run:
python -m pip install -e ".[http,yaml,investing,dev]"

# 4. UTF-8 (Windows console prints NYX's checkmarks) — make it permanent --------
[Environment]::SetEnvironmentVariable("PYTHONUTF8", "1", "User")
$env:PYTHONUTF8 = "1"

# 5. Configuration -------------------------------------------------------------
if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
    Write-Host "Created .env from template (flash model + per-capability memory)." -ForegroundColor Green
    $key = Read-Host "Paste your OLLAMA_API_KEY (leave blank to stay in MOCK mode)"
    if ($key) {
        (Get-Content .env) -replace '^OLLAMA_API_KEY=.*', "OLLAMA_API_KEY=$key" | Set-Content .env
    }
    $ident = Read-Host "SEC EDGAR identity 'Name email' (blank to skip live SEC/investing)"
    if ($ident) {
        (Get-Content .env) -replace '^EDGAR_IDENTITY=.*', "EDGAR_IDENTITY=$ident" | Set-Content .env
    }
}

# 6. MCP servers (factory) — register the full catalog; install binaries as noted
Write-Host "`nRegistering MCP servers (edgartools + research + AI-security)..." -ForegroundColor Yellow
nyx mcp-init --add all
nyx skills          # load the deep skill packs into long-term memory

# 7. Smoke test ----------------------------------------------------------------
Write-Host "`nRunning 'nyx doctor'..." -ForegroundColor Cyan
nyx doctor
Write-Host "`nSetup complete. Optional MCP server binaries: 'uvx paper-search-mcp', " -ForegroundColor Cyan
Write-Host "'npx web-researcher-mcp'; clone hexstrike-ai for AI-security research." -ForegroundColor Cyan

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
