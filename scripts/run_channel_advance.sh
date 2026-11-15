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
set +e
OUTPUT="$("$UV_BIN" run --project "$PROJECT_ROOT" --extra tts politics-channel advance 2>&1)"
STATUS=$?
set -e
printf '%s\n' "$OUTPUT"
if [[ $STATUS -ne 0 ]]; then exit $STATUS; fi
if command -v osascript >/dev/null 2>&1; then
  if printf '%s' "$OUTPUT" | grep -q -- '-> script_pending'; then
    osascript -e 'display notification "A documentary script is ready for your approval. Run politics-channel status." with title "Politics of Everything"' || true
  elif printf '%s' "$OUTPUT" | grep -q -- '-> final_pending'; then
    osascript -e 'display notification "The final render is ready for preview. The private review package arrives Sunday." with title "Politics of Everything"' || true
  fi
fi
