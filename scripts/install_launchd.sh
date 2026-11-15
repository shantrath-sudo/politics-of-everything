#!/bin/zsh
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
AGENT_DIR="$HOME/Library/LaunchAgents"
UID_VALUE="$(id -u)"
DOMAIN="gui/$UID_VALUE"
cd "$PROJECT_ROOT"
mkdir -p "$AGENT_DIR" "$PROJECT_ROOT/data/logs"

FREE_GIB="$(df -Pk "$HOME" | awk 'NR==2 {printf "%.1f", $4/1024/1024}')"
if ! awk -v free="$FREE_GIB" 'BEGIN { exit !(free >= 18) }'; then
  echo "At least 18 GiB free disk space is required before setup. Available: ${FREE_GIB} GiB." >&2
  exit 1
fi

UV_BIN="$(command -v uv || true)"
if [[ -z "$UV_BIN" && -x /opt/homebrew/bin/uv ]]; then
  UV_BIN="/opt/homebrew/bin/uv"
fi
if [[ -z "$UV_BIN" ]]; then
  echo "Install uv first: https://docs.astral.sh/uv/" >&2
  exit 127
fi

for TOOL in ffmpeg ffprobe node npm; do
  if ! command -v "$TOOL" >/dev/null 2>&1; then
    echo "Required tool not found: $TOOL. Install FFmpeg and Node.js before scheduling." >&2
    exit 127
  fi
done

LMS_BIN="$(command -v lms || true)"
if [[ -z "$LMS_BIN" && -x "$HOME/.lmstudio/bin/lms" ]]; then
  LMS_BIN="$HOME/.lmstudio/bin/lms"
fi
if [[ -z "$LMS_BIN" ]]; then
  echo "LM Studio CLI not found. Open LM Studio once and bootstrap lms." >&2
  exit 127
fi
MODEL_KEY="$(sed -n 's/^model_key = "\(.*\)"/\1/p' config/inference.toml)"
if [[ -z "$MODEL_KEY" ]]; then
  echo "No model_key is configured in config/inference.toml." >&2
  exit 1
fi
"$LMS_BIN" load "$MODEL_KEY" --gpu max --context-length 16384 --estimate-only

zsh "$PROJECT_ROOT/scripts/install_tts.sh"
npm ci --prefix "$PROJECT_ROOT/remotion"
npm run build --prefix "$PROJECT_ROOT/remotion"
"$UV_BIN" run --project "$PROJECT_ROOT" --extra tts politics-channel --help >/dev/null

for LABEL in scout advance delivery; do
  TEMPLATE="$PROJECT_ROOT/launchd/com.politics-of-everything.$LABEL.plist.template"
  TARGET="$AGENT_DIR/com.politics-of-everything.$LABEL.plist"
  sed "s|__PROJECT_ROOT__|$PROJECT_ROOT|g" "$TEMPLATE" > "$TARGET"
  launchctl bootout "$DOMAIN" "$TARGET" >/dev/null 2>&1 || true
  launchctl bootstrap "$DOMAIN" "$TARGET"
  launchctl enable "$DOMAIN/com.politics-of-everything.$LABEL"
done

echo "Installed daily topic scouting (08:00), workflow checks (every 4 hours), and Sunday private delivery (09:00 Asia/Kolkata)."
echo "Logs: $PROJECT_ROOT/data/logs/"
echo "No YouTube upload or publication is enabled."
