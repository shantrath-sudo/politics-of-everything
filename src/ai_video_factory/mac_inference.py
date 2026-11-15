"""Small macOS-friendly LM Studio session controller for channel jobs.

This deliberately avoids the upstream Linux/AMD runtime-management layer.
It only starts the loopback server, loads one configured local model, and
unloads that model if this process loaded it. It never updates runtimes.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import urlopen


class MacInferenceError(RuntimeError):
    """Raised when local model setup or readiness checks fail."""


CommandRunner = Callable[..., Any]
HttpGet = Callable[[str, float], str]
MemoryReader = Callable[[], float]
Sleeper = Callable[[float], None]


def _available_memory_gib() -> float:
    try:
        import psutil
    except ImportError as error:
        raise MacInferenceError("psutil is required for the local memory safety check") from error
    return float(psutil.virtual_memory().available) / (1024**3)


def _http_get(url: str, timeout: float) -> str:
    with urlopen(url, timeout=timeout) as response:
        if response.status != 200:
            raise MacInferenceError(f"LM Studio returned HTTP {response.status}")
        return response.read(2 * 1024 * 1024).decode("utf-8", errors="replace")


class MacInferenceSession:
    """Manage one local LM Studio model without touching other loaded models."""

    def __init__(
        self,
        *,
        model_key: str,
        identifier: str,
        context_length: int = 16_384,
        gpu: str = "max",
        ttl_seconds: int = 3_600,
        minimum_available_memory_gib: float = 8.0,
        lms_binary: str = "lms",
        base_url: str = "http://127.0.0.1:1234/v1",
        command_runner: CommandRunner = subprocess.run,
        http_get: HttpGet = _http_get,
        memory_reader: MemoryReader = _available_memory_gib,
        sleeper: Sleeper = time.sleep,
        ready_timeout_seconds: float = 600.0,
        poll_interval_seconds: float = 2.0,
    ) -> None:
        parsed_endpoint = urlsplit(base_url)
        if (
            parsed_endpoint.scheme != "http"
            or parsed_endpoint.hostname != "127.0.0.1"
            or parsed_endpoint.port != 1234
            or parsed_endpoint.path.rstrip("/") != "/v1"
            or parsed_endpoint.username
            or parsed_endpoint.password
            or parsed_endpoint.query
            or parsed_endpoint.fragment
        ):
            raise MacInferenceError("LM Studio must use the configured loopback endpoint")
        self.model_key = model_key
        self.identifier = identifier
        self.context_length = context_length
        self.gpu = gpu
        self.ttl_seconds = ttl_seconds
        self.minimum_available_memory_gib = minimum_available_memory_gib
        self.lms_binary = lms_binary
        self.base_url = base_url.rstrip("/")
        self.server_root = f"{parsed_endpoint.scheme}://{parsed_endpoint.netloc}"
        self.command_runner = command_runner
        self.http_get = http_get
        self.memory_reader = memory_reader
        self.sleeper = sleeper
        self.ready_timeout_seconds = ready_timeout_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self.started_model = False
        self.api_model_id: str | None = None
        self._binary: str | None = None

    def _resolve_binary(self) -> str:
        if self._binary:
            return self._binary
        if self.command_runner is not subprocess.run:
            self._binary = self.lms_binary
            return self._binary
        found = shutil.which(self.lms_binary)
        if not found:
            fallback = Path.home() / ".lmstudio" / "bin" / "lms"
            if fallback.is_file():
                found = str(fallback)
        if not found:
            raise MacInferenceError(
                "LM Studio CLI was not found. Open LM Studio once and run its lms bootstrap command."
            )
        self._binary = found
        return found

    def _run(self, args: Sequence[str], timeout: float = 60.0) -> str:
        command = [self._resolve_binary(), *args]
        try:
            result = self.command_runner(
                command, capture_output=True, text=True, timeout=timeout, check=False
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise MacInferenceError(f"LM Studio command failed: {error}") from error
        if result.returncode != 0:
            detail = (getattr(result, "stderr", "") or getattr(result, "stdout", "") or "").strip()
            raise MacInferenceError(
                f"LM Studio command exited {result.returncode}: {detail[:400]}"
            )
        return (getattr(result, "stdout", "") or "").strip()

    def _models(self) -> list[str] | None:
        try:
            payload = json.loads(self.http_get(f"{self.server_root}/api/v1/models", 5.0))
        except (OSError, URLError, TimeoutError, ValueError, MacInferenceError):
            return None
        models = payload.get("models")
        if not isinstance(models, list):
            return None
        loaded_ids: list[str] = []
        for model in models:
            if not isinstance(model, dict):
                continue
            instances = model.get("loaded_instances", [])
            if not isinstance(instances, list):
                continue
            for instance in instances:
                if isinstance(instance, dict) and isinstance(instance.get("id"), str):
                    loaded_ids.append(instance["id"])
        return loaded_ids

    def _wait_for_server(self) -> list[str]:
        deadline = time.monotonic() + min(self.ready_timeout_seconds, 45.0)
        while time.monotonic() < deadline:
            models = self._models()
            if models is not None:
                return models
            self.sleeper(self.poll_interval_seconds)
        raise MacInferenceError("LM Studio loopback server did not become ready")

    def start(self) -> str:
        available = self.memory_reader()
        if available < self.minimum_available_memory_gib:
            raise MacInferenceError(
                f"available memory {available:.1f} GiB is below the "
                f"{self.minimum_available_memory_gib:.1f} GiB safety threshold"
            )

        models = self._models()
        if models is None:
            self._run(["server", "start", "--port", "1234"])
            models = self._wait_for_server()

        if self.identifier in models:
            self.api_model_id = self.identifier
            return self.api_model_id
        if self.model_key in models:
            self.api_model_id = self.model_key
            return self.api_model_id
        if models:
            raise MacInferenceError(
                "another LM Studio model is already loaded; unload it or use the configured Politics of Everything model before continuing"
            )

        self._run([
            "load", self.model_key,
            "--gpu", self.gpu,
            "--context-length", str(self.context_length),
            "--ttl", str(self.ttl_seconds),
            "--identifier", self.identifier,
        ], timeout=self.ready_timeout_seconds)

        deadline = time.monotonic() + self.ready_timeout_seconds
        while time.monotonic() < deadline:
            models = self._models()
            if models is not None:
                if self.identifier in models:
                    self.started_model = True
                    self.api_model_id = self.identifier
                    return self.api_model_id
                if self.model_key in models:
                    self.started_model = True
                    self.api_model_id = self.model_key
                    return self.api_model_id
            self.sleeper(self.poll_interval_seconds)
        raise MacInferenceError("loaded model did not appear in LM Studio /v1/models")

    def stop(self) -> None:
        if self.started_model:
            self._run(["unload", self.api_model_id or self.identifier], timeout=120.0)
            self.started_model = False

    def __enter__(self) -> str:
        return self.start()

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        self.stop()
        return False
