#!/bin/zsh
set -euo pipefail
UID_VALUE="$(id -u)"
DOMAIN="gui/$UID_VALUE"
AGENT_DIR="$HOME/Library/LaunchAgents"
for LABEL in scout advance delivery; do
  PLIST="$AGENT_DIR/com.politics-of-everything.$LABEL.plist"
  launchctl bootout "$DOMAIN" "$PLIST" >/dev/null 2>&1 || true
  rm -f "$PLIST"
done
echo "Removed Politics of Everything launchd jobs. Project files and production data were not deleted."
