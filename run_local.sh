#!/usr/bin/env bash
set -euo pipefail

HOST="${CORENEW_HOST:-127.0.0.1}"
PORT="${CORENEW_PORT:-7860}"
PYTHON_BIN="${CORENEW_PYTHON:-python}"

if [[ -z "${CORENEW_PYTHON:-}" && -x "$HOME/anaconda3/envs/thesis/bin/python" ]]; then
  PYTHON_BIN="$HOME/anaconda3/envs/thesis/bin/python"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

"$PYTHON_BIN" ui_app.py --host "$HOST" --port "$PORT" --home-path /run/setup
