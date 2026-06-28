#!/usr/bin/env bash
set -e

# Detect if we're running under Rosetta. If not, force x86_64
# since the venv packages are x86_64.
if [ "$(sysctl -n sysctl.proc_translated 2>/dev/null)" != "1" ]; then
    if [ "$(uname -m)" = "arm64" ]; then
        echo "⚠️  Rosetta not active, forcing x86_64 mode..."
        exec arch -x86_64 /bin/bash "$0" "$@"
    fi
fi

cd "$(dirname "$0")"
echo "🚀 Starting CRM server on http://localhost:8000"
exec python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
