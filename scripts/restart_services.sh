#!/usr/bin/env bash
# Restart the full stack.
#
# Thin wrapper around restart_services.py, which owns the actual
# logic: scan both address families, kill whatever holds the
# stack's ports, then start the services. Keeping one
# implementation means the two entry points cannot drift apart.
#
# Usage: bash scripts/restart_services.sh [--no-web] [--python-only] [--gateway-only]

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

exec venv/Scripts/python.exe scripts/restart_services.py "$@"
