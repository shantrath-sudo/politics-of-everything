#!/bin/zsh
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
AGENT_DIR="$HOME/Library/LaunchAgents"
UID_VALUE="$(id -u)"
DOMAIN="gui/$UID_VALUE"
cd "$PROJECT_ROOT"
mkdir -p "$AGENT_DIR" "$PROJECT_ROOT/data/logs"

UV_BIN="$(command -v uv || true)"
if [[ -z "$UV_BIN" && -x /opt/homebrew/bin/uv ]]; then
  UV_BIN="/opt/homebrew/bin/uv"
fi
if [[ -z "$UV_BIN" ]]; then
  echo "Install uv first: https://docs.astral.sh/uv/" >&2
  exit 127
fi

zsh "$PROJECT_ROOT/scripts/install_tts.sh"

for TOOL in ffmpeg ffprobe node npm; do
  if ! command -v "$TOOL" >/dev/null 2>&1; then
    echo "Required tool not found: $TOOL. Install FFmpeg and Node.js before scheduling." >&2
    exit 127
  fi
done

npm ci --prefix "$PROJECT_ROOT/remotion"
npm run build --prefix "$PROJECT_ROOT/remotion"
"$UV_BIN" run --project "$PROJECT_ROOT" --extra tts politics-channel --help >/dev/null

LMS_BIN="$(command -v lms || true)"
if [[ -z "$LMS_BIN" && -x "$HOME/.lmstudio/bin/lms" ]]; then
  LMS_BIN="$HOME/.lmstudio/bin/lms"
fi
if [[ -z "$LMS_BIN" ]]; then
  echo "LM Studio CLI not found. Open LM Studio once and bootstrap lms." >&2
  exit 127
fi
MODEL_KEY="$("$UV_BIN" run --project "$PROJECT_ROOT" --extra tts python -c 'import tomllib; print(tomllib.load(open("config/inference.toml", "rb"))["model_key"])')"
"$LMS_BIN" load "$MODEL_KEY" --gpu max --context-length 16384 --estimate-only -y

for LABEL in scout advance delivery; do
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
