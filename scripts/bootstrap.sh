#!/usr/bin/env bash
# NYX bootstrap for Linux/macOS dev boxes (the mini-PC uses setup-windows11.ps1).
set -euo pipefail

echo "=== NYX Dark Factory — bootstrap ==="

python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[http,yaml,dev]"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env (MOCK mode until you add OLLAMA_API_KEY)."
fi

echo "Running doctor..."
nyx doctor

echo "Running tests..."
pytest -q

echo "=== Bootstrap complete ==="
echo "Try: nyx build \"Add a usage-based billing dashboard\" --autonomy autonomous"
