#!/usr/bin/env bash
# ============================================================================
# NYX — Autonomous Dark Factory : one-shot installer (Linux / macOS)
# The Windows 11 mini-PC uses scripts/setup-windows11.ps1.
#
#   ./install.sh                 full install (venv + investing extras + dev)
#   ./install.sh --minimal       core only (mock mode, zero extra deps)
#   ./install.sh --no-tests      skip the test run
#
# Idempotent: safe to re-run. Leaves you ready to `nyx run "<objective>"`.
# ============================================================================
set -euo pipefail

MINIMAL=0
RUN_TESTS=1
for arg in "$@"; do
  case "$arg" in
    --minimal)  MINIMAL=1 ;;
    --no-tests) RUN_TESTS=0 ;;
    -h|--help)  grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

cd "$(dirname "$0")"
echo "=== NYX Dark Factory — installer ==="

# 1. Python version guard (>= 3.10)
PY="${PYTHON:-python3}"
if ! "$PY" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3,10) else 1)'; then
  echo "ERROR: Python 3.10+ required (found: $("$PY" --version 2>&1))." >&2
  exit 1
fi
echo "Python: $("$PY" --version 2>&1)"

# 2. Virtual environment
if [ ! -d .venv ]; then
  "$PY" -m venv .venv
  echo "Created .venv"
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip >/dev/null

# 3. Dependencies
if [ "$MINIMAL" -eq 1 ]; then
  echo "Installing core (mock mode, dependency-free)…"
  python -m pip install -e .
else
  echo "Installing NYX + investing + dev extras…"
  python -m pip install -e ".[investing,dev]"
fi

# 4. Config
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env (MOCK mode until you set OLLAMA_API_KEY)."
fi

# 5. Load the shipped skill packs into long-term memory
echo "Loading skill packs into memory…"
nyx skills >/dev/null || true

# 6. Health + readiness
echo; echo "--- nyx doctor ---";    nyx doctor    || true
echo; echo "--- nyx preflight ---"; nyx preflight || true

# 7. Tests
if [ "$MINIMAL" -eq 0 ] && [ "$RUN_TESTS" -eq 1 ]; then
  echo; echo "--- tests ---"; pytest -q
fi

cat <<'DONE'

=== Install complete ===
Next:
  source .venv/bin/activate
  # (optional, to go live) edit .env: OLLAMA_API_KEY, EDGAR_IDENTITY, then:
  nyx preflight --probe
  nyx run "Find deep-value companies; learn from Buffett" --autonomy autonomous --keep-going
  nyx eval          # held-out score trend    nyx track   # realized outcomes
Docs: docs/RUNBOOK.md  ·  README.md
DONE
