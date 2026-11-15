from types import SimpleNamespace
from urllib.error import URLError

import pytest

from ai_video_factory.mac_inference import MacInferenceError, MacInferenceSession


def _runner(calls):
    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    return run


def test_preloaded_model_is_reused_and_not_unloaded():
    calls = []
    session = MacInferenceSession(
        model_key="local/qwen.gguf",
        identifier="poe-qwen35-4b",
        command_runner=_runner(calls),
        http_get=lambda _url, _timeout: '{"data":[{"id":"poe-qwen35-4b"}]}',
        memory_reader=lambda: 12.0,
    )
    assert session.start() == "poe-qwen35-4b"
    session.stop()
    assert calls == []
    assert session.started_model is False


def test_session_loads_and_unloads_only_its_model():
    calls = []
    responses = iter([
        '{"data":[]}',
        '{"data":[{"id":"poe-qwen35-4b"}]}',
    ])
    session = MacInferenceSession(
        model_key="local/qwen.gguf",
        identifier="poe-qwen35-4b",
        command_runner=_runner(calls),
        http_get=lambda _url, _timeout: next(responses),
        memory_reader=lambda: 12.0,
        sleeper=lambda _seconds: None,
    )
    assert session.start() == "poe-qwen35-4b"
    assert session.started_model is True
    session.stop()
    assert calls[0][1] == "load"
    assert calls[-1] == ["lms", "unload", "poe-qwen35-4b"]
    assert session.started_model is False


def test_session_starts_server_when_loopback_is_unavailable():
    calls = []
    responses = iter([
        None,
        '{"data":[]}',
        '{"data":[{"id":"poe-qwen35-4b"}]}',
    ])

    def http_get(_url, _timeout):
        value = next(responses)
        if value is None:
            raise URLError("connection refused")
        return value

    session = MacInferenceSession(
        model_key="local/qwen.gguf",
        identifier="poe-qwen35-4b",
        command_runner=_runner(calls),
        http_get=http_get,
        memory_reader=lambda: 12.0,
        sleeper=lambda _seconds: None,
    )
    session.start()
    assert calls[0][1:4] == ["server", "start", "--port"]
    assert calls[1][1] == "load"


def test_session_refuses_to_load_below_memory_gate():
    calls = []
    session = MacInferenceSession(
        model_key="local/qwen.gguf",
        identifier="poe-qwen35-4b",
        command_runner=_runner(calls),
        http_get=lambda _url, _timeout: '{"data":[]}',
        memory_reader=lambda: 7.9,
    )
    with pytest.raises(MacInferenceError, match="below the 8.0 GiB safety threshold"):
        session.start()
    assert calls == []


def test_session_rejects_non_loopback_endpoint():
    with pytest.raises(MacInferenceError, match="loopback endpoint"):
        MacInferenceSession(
            model_key="local/qwen.gguf",
            identifier="poe-qwen35-4b",
            base_url="http://0.0.0.0:1234/v1",
        )


def test_session_rejects_nonstandard_loopback_paths():
    with pytest.raises(MacInferenceError, match="loopback endpoint"):
        MacInferenceSession(
            model_key="local/qwen.gguf",
            identifier="poe-qwen35-4b",
            base_url="http://127.0.0.1:1234/v1/other",
        )
