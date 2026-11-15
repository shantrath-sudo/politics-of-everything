#!/bin/zsh
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew is required for the one-command Mac bootstrap." >&2
  echo "Install Homebrew from https://brew.sh/ and rerun this script." >&2
  exit 127
fi

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

for PACKAGE in uv ffmpeg node; do
  if ! brew list --formula "$PACKAGE" >/dev/null 2>&1; then
    echo "Installing $PACKAGE..."
    brew install "$PACKAGE"
  else
    echo "$PACKAGE is already installed."
  fi
done

uv python install 3.12

if ! command -v lms >/dev/null 2>&1 && [[ ! -x "$HOME/.lmstudio/bin/lms" ]]; then
  echo "Install and open LM Studio, then run its documented 'lms bootstrap' command." >&2
  echo "After that, rerun: zsh scripts/bootstrap_mac.sh" >&2
  exit 127
fi

SYSTEM_OFFSET="$(env -u TZ date +%z)"
if [[ "$SYSTEM_OFFSET" != "+0530" ]]; then
  echo "Set the Mac system time zone to Asia/Kolkata (UTC+05:30) before setup." >&2
  exit 1
fi

echo "Checking disk space and downloading the configured local 4B text model..."
zsh "$PROJECT_ROOT/scripts/install_local_model.sh"

echo "Installing Python dependencies, local Kokoro narration, Remotion and launchd jobs..."
zsh "$PROJECT_ROOT/scripts/install_launchd.sh"

echo
echo "Politics of Everything local automation is installed."
echo "Daily scout: 08:00 Asia/Kolkata"
echo "Workflow advancement: every four hours"
echo "Private Sunday review package: 09:00 Asia/Kolkata"
echo "No YouTube upload or publication is enabled."
