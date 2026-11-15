#!/usr/bin/env python3
"""Run a real local Kokoro speech synthesis smoke test."""
from __future__ import annotations

from pathlib import Path

from ai_video_factory.narration import synthesize_to_wav

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "health-check" / "kokoro-smoke-test.wav"


def main() -> int:
    metadata: dict[str, object] = {}
    synthesize_to_wav(
        "This is a voice quality and timing check for Politics of Everything.",
        OUTPUT,
        engine="kokoro",
        voice="af_heart",
        metadata=metadata,
    )
    if not OUTPUT.is_file() or OUTPUT.stat().st_size < 8_000:
        raise RuntimeError("Kokoro smoke test did not produce a valid WAV file")
    print(f"TTS ready: {OUTPUT} ({metadata})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
