#!/bin/zsh
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UV_BIN="$(command -v uv || true)"
if [[ -z "$UV_BIN" && -x /opt/homebrew/bin/uv ]]; then
  UV_BIN="/opt/homebrew/bin/uv"
fi
if [[ -z "$UV_BIN" ]]; then
  echo "uv is not installed; run scripts/install_launchd.sh after installing uv." >&2
  exit 127
fi
mkdir -p "$PROJECT_ROOT/data/logs"
cd "$PROJECT_ROOT"
"$UV_BIN" run --project "$PROJECT_ROOT" --extra tts politics-channel advance
