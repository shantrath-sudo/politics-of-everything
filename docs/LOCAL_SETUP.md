# Local Setup — Apple Silicon Mac

This is the one-time setup path. Do not run the scheduler until all checks below pass.

## 1. Required tools

- macOS on Apple Silicon
- Python 3.12
- uv
- FFmpeg and ffprobe
- Node.js and npm for the Remotion renderer
- LM Studio 0.4.0 or newer, opened at least once, with its CLI bootstrapped

LM Studio's CLI is distributed with the desktop app. Its documented bootstrap and local model commands are at https://lmstudio.ai/docs/cli.

## 2. Install the local language model

The configured model is the LM Studio Community Qwen3.5 4B GGUF, Q4_K_M quantization (about 2.71 GB). It is text-only for this workflow; do not download the optional image projector.

Run:

    zsh scripts/install_local_model.sh

Then inspect:

    lms ls

The configured model key is in config/inference.toml. If LM Studio reports a different key, update model_key to the exact key shown by lms ls. The controller assigns the stable API identifier poe-qwen35-4b when it loads the model.

The model is published by LM Studio Community at https://huggingface.co/lmstudio-community/Qwen3.5-4B-GGUF. The model card declares Apache-2.0.

## 3. Install local narration

The default narrator is Kokoro ONNX. Install the Python extra, download the pinned ONNX and voice files, verify their SHA-256 hashes, and generate a test WAV:

    zsh scripts/install_tts.sh

The model and voice files total roughly 353 MiB. Their upstream release and checksums are recorded in scripts/download_tts_models.py. The Kokoro model is distributed under Apache-2.0; see https://github.com/thewh1teagle/kokoro-onnx/releases.

## 4. Install the project and schedules

Before scheduling, make sure FFmpeg, ffprobe, Node.js and npm are available, and install the Remotion dependencies from the remotion directory using its checked-in lockfile.

Then run:

    zsh scripts/install_launchd.sh

This installs Python dependencies and Kokoro if not already installed, checks the CLI, and registers:
- daily topic scouting at 08:00 Asia/Kolkata
- approval-gated workflow advancement every four hours
- private final-review package assembly every Sunday at 09:00

Keep at least 12 GiB free on the startup disk for render intermediates and safety headroom. The status command reports free disk space. The Mac must be awake and the user session available. Logs are stored under data/logs/.

To remove the schedules without deleting project data:

    zsh scripts/uninstall_launchd.sh

## 5. How local inference is controlled

The channel uses a small macOS-specific LM Studio controller. It:
- checks available memory before loading the model
- uses only the loopback API at 127.0.0.1:1234
- starts the local server if it is not already running
- loads only the configured model with a stable identifier
- unloads only the model it loaded itself
- does not update or replace LM Studio runtimes

Keep the LM Studio server on its default localhost binding; do not enable LAN/network sharing. The local integration assumes authentication is disabled for this loopback-only service. The controller never uploads prompts or source material to a hosted API.

## 6. First verification

Run:

    politics-channel scout
    politics-channel status

After a topic is explicitly approved, the scheduled advance command performs research and script drafting, then pauses for script approval. After script approval it renders and pauses for final approval.

No YouTube upload or publication is performed.
