# Deploying NYX on a Windows 11 Mini‑PC

The whole dark factory is designed to live on a single fanless mini‑PC. The
heavy cognition runs in **Ollama Cloud**, so the local box only needs to
orchestrate — meaning a modest mini‑PC (e.g. 16 GB RAM, no discrete GPU) is
plenty. The GPUs live in the cloud; your corner of the room stays quiet.

## Why a mini‑PC + Ollama Cloud

- **Always‑on, low‑power.** A dark factory operates 24/7; a mini‑PC sips watts.
- **No data center, no ops team.** Capability without infrastructure headcount.
- **Cloud brain, local body.** [Ollama Cloud](https://docs.ollama.com/cloud)
  gives you frontier‑class models (Qwen 3.5, GLM‑5.1, DeepSeek‑V4, Gemma 4, …)
  with **no prompt/response logging or training on your data**, billed by usage
  on Free / Pro ($20) / Max ($100) plans.

## Hardware baseline

| | Minimum | Comfortable |
| --- | --- | --- |
| CPU | 4 cores | 8+ cores |
| RAM | 8 GB | 16–32 GB |
| Disk | 20 GB free | 256 GB SSD |
| GPU | none (cloud brain) | none required |
| Network | stable broadband | wired ethernet |

## One‑shot install

Open **PowerShell as Administrator** and run:

```powershell
# Allow the script for this session, then run the installer
Set-ExecutionPolicy -Scope Process Bypass -Force
./scripts/setup-windows11.ps1
```

The script will:

1. Install **winget** prerequisites (Git, Python 3.11+).
2. Optionally install the **Ollama** desktop app (for local fallback models).
3. Create a virtual environment and `pip install -e .`.
4. Copy `.env.example` → `.env` and prompt for your `OLLAMA_API_KEY`.
5. Run a smoke test (`nyx doctor`).
6. Optionally register NYX as a **scheduled task** so the factory starts on boot
   and runs lights‑out.

## Manual install

```powershell
winget install --id Git.Git -e
winget install --id Python.Python.3.11 -e

git clone <your-fork-url> nyx
cd nyx
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[http,yaml]"

Copy-Item .env.example .env
notepad .env          # paste your OLLAMA_API_KEY

nyx doctor            # verify config + brain connectivity
```

## Running lights‑out

```powershell
# Foreground, supervised (you approve deploys)
nyx build "Ship a waitlist landing page with email capture"

# Fully autonomous within policy, as a background service
$env:NYX_AUTONOMY = "autonomous"
nyx serve
```

Register as a boot service so the factory is always on:

```powershell
$action  = New-ScheduledTaskAction -Execute "powershell.exe" `
  -Argument "-WindowStyle Hidden -Command `"cd C:\nyx; .\.venv\Scripts\Activate.ps1; nyx serve`""
$trigger = New-ScheduledTaskTrigger -AtStartup
Register-ScheduledTask -TaskName "NYX Dark Factory" -Action $action -Trigger $trigger -RunLevel Highest
```

## Operating it

```powershell
nyx status            # current runs and gate states
nyx ledger --tail 50  # audit trail
nyx metrics           # throughput, cost, gate pass-rate, evolution gains
nyx evolve -g 5       # run 5 generations of self-improvement overnight
```

## Hardening checklist

- Store `OLLAMA_API_KEY` in `.env` (git‑ignored) or Windows Credential Manager.
- Keep `NYX_CONSTITUTION_MODE=block` (fail‑closed) in production.
- Start at `NYX_AUTONOMY=supervised`; graduate to `autonomous` only after the
  audit ledger shows a clean track record.
- Back up `.nyx/` (ledger + evolution archive) — that is your company's memory.
