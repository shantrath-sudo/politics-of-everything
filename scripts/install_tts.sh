#!/bin/zsh
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UV_BIN="$(command -v uv || true)"
if [[ -z "$UV_BIN" && -x /opt/homebrew/bin/uv ]]; then
  UV_BIN="/opt/homebrew/bin/uv"
fi
if [[ -z "$UV_BIN" ]]; then
  echo "Install uv first: https://docs.astral.sh/uv/" >&2
  exit 127
fi
cd "$PROJECT_ROOT"
"$UV_BIN" sync --project "$PROJECT_ROOT" --extra tts
"$UV_BIN" run --project "$PROJECT_ROOT" python scripts/download_tts_models.py
"$UV_BIN" run --project "$PROJECT_ROOT" python scripts/check_tts.py
