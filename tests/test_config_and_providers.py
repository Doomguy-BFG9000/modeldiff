from __future__ import annotations

import io
import json
import urllib.error

import pytest

from modeldiff.cases import TestCase
from modeldiff.config import load_config, parse_config
from modeldiff.errors import ProviderError, ValidationError
from modeldiff.providers import OllamaProvider, ReplayProvider, build_provider

CASE = TestCase(
    id="c1", type="exact", input="Say hi", expected="hi", generation={"temperature": 0.5}
)


# --- config ------------------------------------------------------------------


def test_replay_config_resolves_outputs_relative_to_config(write_yaml, write_json):
    write_json("rec/out.json", {"outputs": {"c1": "hi"}})
    cfg = load_config(
        write_yaml("cfg/base.yaml", {"id": "b", "provider": "replay", "outputs": "../rec/out.json"})
    )
    provider = build_provider(cfg)
    assert provider.generate(CASE).output == "hi"


@pytest.mark.parametrize(
    ("data", "fragment"),
    [
        ({"id": "x", "provider": "replay"}, "'outputs' is a required property"),
        ({"id": "x", "provider": "ollama"}, "'model' is a required property"),
        ({"id": "x", "provider": "openai", "model": "m"}, "provider"),
        (
            {"id": "x", "provider": "replay", "outputs": "o.json", "modle": "m"},
            "'modle' was unexpected",
        ),
        (
            {"id": "x", "provider": "replay", "outputs": "o.json", "capture_output": "some"},
            "capture_output",
        ),
        ({"provider": "replay", "outputs": "o.json"}, "'id' is a required property"),
        (
            {"id": "x", "provider": "ollama", "model": "m", "base_url": "localhost:11434"},
            "base_url",
        ),
    ],
)
def test_invalid_configs(data, fragment):
    with pytest.raises(ValidationError) as exc:
        parse_config(data, "cfg.yaml")
    assert any(fragment in p for p in exc.value.problems), exc.value.problems


def test_config_must_be_mapping():
    with pytest.raises(ValidationError, match="top level must be a mapping"):
        parse_config(["id"], "cfg.yaml")


def test_secret_like_keys_are_redacted():
    cfg = parse_config(
        {
            "id": "x",
            "provider": "ollama",
            "model": "m",
            "metadata": {"api_key": "sk-123", "nested": {"Auth_Token": "t"}, "owner": "me"},
        }
    )
    public = cfg.public_dict()
    assert public["metadata"] == {
        "api_key": "<redacted>",
        "nested": {"Auth_Token": "<redacted>"},
        "owner": "me",
    }
    assert "sk-123" not in json.dumps(public)


# --- replay ------------------------------------------------------------------


def test_replay_missing_case_raises_provider_error(write_json):
    provider = ReplayProvider(write_json("o.json", {"outputs": {}}))
    with pytest.raises(ProviderError, match="no recorded output for case 'c1'"):
        provider.generate(CASE)


def test_replay_returns_recorded_latency_and_metadata(write_json):
    path = write_json(
        "o.json", {"outputs": {"c1": {"output": "hi", "latency_ms": 12.5, "metadata": {"k": 1}}}}
    )
    response = ReplayProvider(path).generate(CASE)
    assert (response.output, response.recorded_latency_ms, response.metadata) == (
        "hi",
        12.5,
        {"k": 1},
    )


@pytest.mark.parametrize(
    "data",
    [
        {"results": {}},
        {"outputs": {"c1": 5}},
        {"outputs": {"c1": {"text": "x"}}},
        {"outputs": {"c1": {"output": "x", "latency_ms": -1}}},
    ],
)
def test_replay_rejects_malformed_files(write_json, data):
    with pytest.raises(ValidationError):
        ReplayProvider(write_json("o.json", data))


# --- ollama (mocked; no server or model needed) ---------------------------------


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_ollama_sends_prompt_and_merged_options(monkeypatch):
    seen = {}

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["body"] = json.loads(request.data)
        seen["timeout"] = timeout
        body = {
            "model": "m",
            "response": "hi",
            "eval_count": 3,
            "total_duration": 10,
            "context": [1, 2],
        }
        return FakeResponse(json.dumps(body).encode())

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    provider = OllamaProvider(
        "m", "http://localhost:11434/", options={"temperature": 0, "seed": 1}, timeout_s=9
    )
    response = provider.generate(CASE)

    assert response.output == "hi"
    assert response.metadata == {"model": "m", "eval_count": 3, "total_duration": 10}
    assert seen["url"] == "http://localhost:11434/api/generate"
    assert seen["timeout"] == 9
    assert seen["body"] == {
        "model": "m",
        "prompt": "Say hi",
        "stream": False,
        "options": {"temperature": 0.5, "seed": 1},  # case generation overrides config
    }


def test_ollama_connection_refused(monkeypatch):
    def fake_urlopen(request, timeout):
        raise urllib.error.URLError(ConnectionRefusedError("refused"))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    with pytest.raises(ProviderError, match="could not reach Ollama .* is `ollama serve` running"):
        OllamaProvider("m").generate(CASE)


def test_ollama_http_error_includes_body(monkeypatch):
    def fake_urlopen(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url, 404, "nf", {}, io.BytesIO(b'{"error":"model not found"}')
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    with pytest.raises(ProviderError, match="HTTP 404: .*model not found"):
        OllamaProvider("m").generate(CASE)


def test_ollama_timeout(monkeypatch):
    def fake_urlopen(request, timeout):
        raise TimeoutError("timed out")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    with pytest.raises(ProviderError, match="could not reach Ollama"):
        OllamaProvider("m").generate(CASE)


@pytest.mark.parametrize(
    ("body", "fragment"),
    [
        (b"<html>", "not JSON"),
        (b'{"error": "boom"}', "Ollama error: boom"),
        (b"{}", "no 'response' text"),
    ],
)
def test_ollama_bad_responses(monkeypatch, body, fragment):
    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout: FakeResponse(body))
    with pytest.raises(ProviderError, match=fragment):
        OllamaProvider("m").generate(CASE)


def test_ollama_describe_tolerates_missing_server(monkeypatch):
    def fake_urlopen(request, timeout):
        raise urllib.error.URLError("down")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    assert OllamaProvider("m").describe() == {
        "provider": "ollama",
        "model": "m",
        "base_url": "http://localhost:11434",
    }
