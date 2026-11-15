#!/bin/zsh
set -euo pipefail
LMS_BIN="$(command -v lms || true)"
if [[ -z "$LMS_BIN" && -x "$HOME/.lmstudio/bin/lms" ]]; then
  LMS_BIN="$HOME/.lmstudio/bin/lms"
fi
if [[ -z "$LMS_BIN" ]]; then
  echo "LM Studio CLI was not found. Open LM Studio once, then run its lms bootstrap command." >&2
  exit 127
fi

"$LMS_BIN" get "https://huggingface.co/lmstudio-community/Qwen3.5-4B-GGUF@Q4_K_M"
echo
echo "Downloaded the 4-bit Qwen3.5 4B model."
echo "Confirm the model key with:"
"$LMS_BIN" ls
echo
echo "The configured key is in config/inference.toml. If lms ls shows a different key,"
echo "update model_key there before installing launchd schedules."
