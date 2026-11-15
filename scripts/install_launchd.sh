#!/bin/zsh
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
AGENT_DIR="$HOME/Library/LaunchAgents"
UID_VALUE="$(id -u)"
DOMAIN="gui/$UID_VALUE"
mkdir -p "$AGENT_DIR" "$PROJECT_ROOT/data/logs"

UV_BIN="$(command -v uv || true)"
if [[ -z "$UV_BIN" && -x /opt/homebrew/bin/uv ]]; then
  UV_BIN="/opt/homebrew/bin/uv"
fi
if [[ -z "$UV_BIN" ]]; then
  echo "Install uv first: https://docs.astral.sh/uv/" >&2
  exit 127
fi

"$UV_BIN" sync --project "$PROJECT_ROOT" --dev
"$UV_BIN" run --project "$PROJECT_ROOT" politics-channel --help >/dev/null

for LABEL in scout advance; do
  TEMPLATE="$PROJECT_ROOT/launchd/com.politics-of-everything.$LABEL.plist.template"
  TARGET="$AGENT_DIR/com.politics-of-everything.$LABEL.plist"
  sed "s|__PROJECT_ROOT__|$PROJECT_ROOT|g" "$TEMPLATE" > "$TARGET"
  launchctl bootout "$DOMAIN" "$TARGET" >/dev/null 2>&1 || true
  launchctl bootstrap "$DOMAIN" "$TARGET"
  launchctl enable "$DOMAIN/com.politics-of-everything.$LABEL"
done

echo "Installed daily topic scouting (08:00 Asia/Kolkata) and approval-gated workflow checks (every 4 hours)."
echo "Logs: $PROJECT_ROOT/data/logs/"
echo "These jobs do not upload or publish videos."
