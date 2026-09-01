#!/usr/bin/env bash
# NYX bootstrap (Linux/macOS). Kept for back-compat — delegates to ./install.sh,
# the canonical one-shot installer. The mini-PC uses setup-windows11.ps1.
set -euo pipefail
cd "$(dirname "$0")/.."
exec ./install.sh "$@"
