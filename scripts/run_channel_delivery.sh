#!/bin/zsh
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UV_BIN="$(command -v uv || true)"
if [[ -z "$UV_BIN" && -x /opt/homebrew/bin/uv ]]; then
  UV_BIN="/opt/homebrew/bin/uv"
fi
if [[ -z "$UV_BIN" ]]; then
  echo "uv is not installed." >&2
  exit 127
fi
mkdir -p "$PROJECT_ROOT/data/logs"
cd "$PROJECT_ROOT"
OUTPUT="$("$UV_BIN" run --project "$PROJECT_ROOT" --extra tts politics-channel deliver 2>&1)"
printf '%s\n' "$OUTPUT"
if command -v osascript >/dev/null 2>&1 && printf '%s' "$OUTPUT" | grep -q 'review package ready at'; then
  osascript -e 'display notification "The Sunday documentary review package is ready. No video was published." with title "Politics of Everything"'
fi
