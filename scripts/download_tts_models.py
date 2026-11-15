#!/usr/bin/env python3
"""Download pinned Kokoro ONNX model files and verify SHA-256 before use."""
from __future__ import annotations

import hashlib
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "models" / "tts"
USER_AGENT = "PoliticsOfEverything/1.0 (local TTS setup)"

ASSETS = (
    (
        "kokoro-v1.0.onnx",
        "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.0.onnx",
        "beb0d1848dee9a49da392cc3df26958d46cfa35d321edf434f52949153f0df3a",
    ),
    (
        "voices-v1.0.bin",
        "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/voices-v1.0.bin",
        "bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d",
    ),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(name: str, url: str, expected_hash: str) -> Path:
    DESTINATION.mkdir(parents=True, exist_ok=True)
    target = DESTINATION / name
    if target.is_file() and sha256(target) == expected_hash:
        print(f"Verified existing file: {target}")
        return target
    target.unlink(missing_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    digest = hashlib.sha256()
    size = 0
    with urllib.request.urlopen(request, timeout=90) as response:
        if response.status != 200:
            raise RuntimeError(f"download failed for {name}: HTTP {response.status}")
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=DESTINATION, prefix=f".{name}.", delete=False
        ) as temporary:
            temp_path = Path(temporary.name)
            try:
                while True:
                    block = response.read(1024 * 1024)
                    if not block:
                        break
                    temporary.write(block)
                    digest.update(block)
                    size += len(block)
                temporary.flush()
            except Exception:
                temp_path.unlink(missing_ok=True)
                raise
    actual_hash = digest.hexdigest()
    if actual_hash != expected_hash:
        temp_path.unlink(missing_ok=True)
        raise RuntimeError(
            f"SHA-256 mismatch for {name}: expected {expected_hash}, got {actual_hash}"
        )
    temp_path.replace(target)
    print(f"Downloaded and verified {name} ({size / 1024 / 1024:.1f} MiB)")
    return target


def main() -> int:
    try:
        for asset in ASSETS:
            download(*asset)
    except Exception as error:
        print(f"TTS model setup failed: {error}", file=sys.stderr)
        return 1
    print(f"Kokoro model files ready in {DESTINATION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
