import io
import json

import pytest
from pydantic import ValidationError

from agentguard import model_transport
from agentguard.model import (
    LocalModel,
    ModelConfig,
    ModelFailure,
    inference_environment,
    parse_reply,
)
from agentguard.runtime import turn_schema


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://api.example.com",
        "http://example.com:8101",
        "http://localhost:8101",
        "http://127.0.0.1:8101/v1",
        "http://127.0.0.1:8101?target=external",
        "http://user:password@127.0.0.1:8101",
        "http://192.168.0.10:8101",
        "http://127.0.0.1",
        "http://127.0.0.1:8101#fragment",
    ],
)
def test_adapter_rejects_nonlocal_or_ambiguous_endpoints(endpoint):
    with pytest.raises(ValidationError):
        ModelConfig(endpoint=endpoint)


@pytest.mark.parametrize("endpoint", ["http://127.0.0.1:8101", "http://[::1]:8101"])
def test_literal_loopback_is_accepted(endpoint):
    assert ModelConfig(endpoint=endpoint).endpoint == endpoint


@pytest.mark.parametrize(
    "usage",
    [
        {},
        {"prompt_tokens": 1, "completion_tokens": True},
        {"prompt_tokens": 1, "completion_tokens": -1},
    ],
)
def test_usage_is_required_and_validated(usage):
    with pytest.raises(ModelFailure, match="INVALID_MODEL_RESPONSE"):
        parse_reply(
            json.dumps(
                {
                    "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                    "usage": usage,
                }
            )
        )


def test_tokenization_and_generation_use_same_non_thinking_template(monkeypatch):
    model = LocalModel(ModelConfig())
    calls = []

    def request(path, body, *, timeout):
        calls.append((path, body))
        if path == "/apply-template":
            return '{"prompt":"rendered"}'
        if path == "/tokenize":
            return '{"tokens":[1,2,3]}'
        return "raw"

    monkeypatch.setattr(model, "request", request)
    messages = [{"role": "user", "content": "test"}]
    assert model.count_tokens(messages, timeout=1) == 3
    assert model.complete(messages, {}, max_tokens=25, timeout=1) == "raw"
    assert calls[0][1]["chat_template_kwargs"] == calls[2][1]["chat_template_kwargs"]
    assert calls[2][1]["max_tokens"] == 25
    assert calls[2][1]["cache_prompt"] is False


def test_wire_schema_preserves_discriminator_first_order(monkeypatch):
    def child(command, payload, **kwargs):
        request = json.loads(payload)
        schema = request["body"]["response_format"]["schema"]
        assert list(schema["$defs"]["ActionTurn"]["properties"]) == ["kind", "action"]
        for name in ("ReadAction", "CreateAction"):
            assert list(schema["$defs"][name]["properties"]) == ["tool", "arguments"]
            assert schema["$defs"][name]["required"] == ["tool", "arguments"]
        return b'{"body":"raw"}'

    monkeypatch.setattr("agentguard.model.bounded_process", child)
    assert LocalModel(ModelConfig()).complete([], turn_schema(), max_tokens=5, timeout=1) == "raw"


def test_inference_children_do_not_inherit_credentials_or_runtime_overrides(monkeypatch):
    for key in ("AWS_SECRET_ACCESS_KEY", "OPENAI_API_KEY", "LLAMA_ARG_TOOLS", "PYTHONPATH"):
        monkeypatch.setenv(key, "must-not-reach-model")
    env = inference_environment()
    assert "must-not-reach-model" not in env.values()
    assert env["PYTHONIOENCODING"] == "utf-8"


@pytest.mark.parametrize(
    "status,body,expected",
    [
        (200, b'{"ok":true}', {"body": '{"ok":true}'}),
        (302, b"redirect", {"error": "MODEL_HTTP_REJECTED"}),
        (500, b"private server traceback", {"error": "MODEL_UNAVAILABLE"}),
        (200, b"x" * 65537, {"error": "MODEL_RESPONSE_TOO_LARGE"}),
        (200, b"\xff", {"error": "INVALID_MODEL_RESPONSE"}),
    ],
    ids=["ok", "redirect", "server-error", "oversized", "invalid-utf8"],
)
def test_transport_bounds_response_and_never_follows_redirects(
    monkeypatch, capsys, status, body, expected
):
    calls = []

    class Response:
        def read(self, limit):
            assert limit == 65537
            return body[:limit]

    response = Response()
    response.status = status

    class Connection:
        def __init__(self, host, port, timeout):
            assert host == "127.0.0.1" and port == 8101

        def request(self, *args, **kwargs):
            calls.append(args)

        def getresponse(self):
            return response

        def close(self):
            pass

    payload = json.dumps({"endpoint": "http://127.0.0.1:8101", "path": "/props", "body": None})
    monkeypatch.setattr(
        model_transport.sys, "stdin", io.TextIOWrapper(io.BytesIO(payload.encode()))
    )
    monkeypatch.setattr(model_transport.http.client, "HTTPConnection", Connection)
    model_transport.main()
    assert json.loads(capsys.readouterr().out) == expected
    assert len(calls) == 1
