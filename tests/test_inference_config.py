from pathlib import Path

import pytest
from pydantic import ValidationError

from ai_video_factory.inference_config import InferenceConfig, load_inference_config


def valid_config(**overrides: object) -> dict[str, object]:
    config: dict[str, object] = {
        "schema_version": 1,
        "backend": "lm_studio",
        "base_url": "http://127.0.0.1:1234/v1",
        "lms_binary": "lms",
        "model_key": "qwen3.5-4b-instruct",
        "identifier": "poe-qwen35-4b",
        "context_length": 16_384,
        "gpu": "max",
        "parallel": 1,
        "ttl_seconds": 3_600,
        "minimum_available_memory_gib": 8,
        "models_directory": "~/.lmstudio/models",
        "server_config_path": "~/.lmstudio/.internal/http-server-config.json",
    }
    config.update(overrides)
    return config


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_loads_checked_in_lm_studio_configuration(project_root: Path) -> None:
    config = load_inference_config(project_root / "config" / "inference.toml")
    assert config.schema_version == 1
    assert config.backend == "lm_studio"
    assert config.base_url == "http://127.0.0.1:1234/v1"
    assert config.lms_binary == "lms"
    assert config.model_key == "lmstudio-community/Qwen3.5-4B-GGUF"
    assert config.identifier == "poe-qwen35-4b"
    assert config.context_length == 16_384
    assert config.gpu == "max"
    assert config.parallel == 1
    assert config.ttl_seconds == 3_600
    assert config.minimum_available_memory_gib == 8
    assert config.models_directory == str(Path.home() / ".lmstudio/models")
    assert config.server_config_path == (
        str(Path.home() / ".lmstudio/.internal/http-server-config.json")
    )


@pytest.mark.parametrize(
    "base_url",
    [
        "https://127.0.0.1:1234/v1",
        "http://localhost:1234/v1",
        "http://0.0.0.0:1234/v1",
        "http://127.0.0.1:1234/v1?token=secret",
        "http://user:secret@127.0.0.1:1234/v1",
    ],
)
def test_rejects_noncanonical_or_credentialed_endpoint(base_url: str) -> None:
    with pytest.raises(ValidationError):
        InferenceConfig.model_validate(valid_config(base_url=base_url))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("identifier", "AB"),
        ("models_directory", "relative/models"),
        ("server_config_path", "relative/http-server-config.json"),
        ("context_length", 0),
        ("parallel", 2),
        ("ttl_seconds", 0),
        ("minimum_available_memory_gib", 0),
    ],
)
def test_rejects_invalid_strict_configuration_values(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        InferenceConfig.model_validate(valid_config(**{field: value}))


@pytest.mark.parametrize("field", ["schema_version", "parallel"])
def test_rejects_boolean_numeric_literals(field: str) -> None:
    with pytest.raises(ValidationError):
        InferenceConfig.model_validate(valid_config(**{field: True}))
