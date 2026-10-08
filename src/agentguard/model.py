"""Bounded llama.cpp adapter. Inference is restricted to literal loopback addresses."""

import ipaddress
import json
import os
import sys
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from pydantic import Field, field_validator

from agentguard.computation import ToolFailure
from agentguard.contracts import Contract
from agentguard.supervisor import bounded_process


class ModelFailure(Exception):
    """A bounded reason code, without server bodies or prompts in default logs."""


def inference_environment() -> dict[str, str]:
    """Do not pass business credentials or implicit provider/runtime overrides to inference."""
    allowed: tuple[str, ...] = ("PATH", "TMPDIR", "LANG", "LC_ALL", "LC_CTYPE", "TZ")
    if os.name == "nt":
        allowed += ("SystemRoot", "WINDIR", "TEMP", "TMP")
    return {key: os.environ[key] for key in allowed if key in os.environ} | {
        "PYTHONIOENCODING": "utf-8"
    }


class ModelConfig(Contract):
    endpoint: str = "http://127.0.0.1:8101"
    model: str = "agentguard-qwen3-4b"
    context_tokens: int = Field(default=8192, ge=512, le=32768)
    temperature: float = Field(default=0.7, ge=0, le=2)
    top_p: float = Field(default=0.8, gt=0, le=1)
    top_k: int = Field(default=20, ge=0)
    seed: int = 42
    request_timeout_seconds: float = Field(default=90, gt=0, le=300)

    @field_validator("endpoint")
    @classmethod
    def loopback_only(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "http"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
            or parsed.hostname is None
            or not ipaddress.ip_address(parsed.hostname).is_loopback
            or parsed.port is None
        ):
            raise ValueError("Use http://<literal loopback IP>:<port> without credentials or path")
        return value.rstrip("/")


@dataclass(frozen=True)
class ModelReply:
    content: str
    prompt_tokens: int
    completion_tokens: int
    finish_reason: str


def parse_reply(raw: str) -> ModelReply:
    try:
        envelope = json.loads(raw)
        choices = envelope["choices"]
        if len(choices) != 1:
            raise ValueError
        message = choices[0]["message"]
        content = message["content"]
        usage = envelope["usage"]
        prompt, generated = usage["prompt_tokens"], usage["completion_tokens"]
        finish = choices[0]["finish_reason"]
        if (
            not isinstance(content, str)
            or type(prompt) is not int
            or type(generated) is not int
            or min(prompt, generated) < 0
            or not isinstance(finish, str)
            or message.get("tool_calls")
            or message.get("reasoning_content")
        ):
            raise ValueError
        return ModelReply(content, prompt, generated, finish)
    except (ValueError, KeyError, TypeError, IndexError) as exc:
        raise ModelFailure("INVALID_MODEL_RESPONSE") from exc


class LocalModel:
    def __init__(self, config: ModelConfig):
        self.config = config

    def request(self, path: str, body: dict[str, Any] | None, *, timeout: float) -> str:
        # llama.cpp's grammar uses schema property order. Canonical sorting here
        # would put `action` before `kind`, contradicting our demonstrated protocol.
        payload = json.dumps(
            {"endpoint": self.config.endpoint, "path": path, "body": body},
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
        try:
            raw = bounded_process(
                [sys.executable, "-m", "agentguard.model_transport"],
                payload,
                timeout=min(timeout, self.config.request_timeout_seconds),
                output_limit=131072,
                env=inference_environment(),
            )
        except ToolFailure as exc:
            reason = "MODEL_TIMEOUT" if str(exc) == "TOOL_TIMEOUT" else "MODEL_TRANSPORT_FAILED"
            raise ModelFailure(reason) from exc
        envelope = json.loads(raw)
        if "error" in envelope:
            raise ModelFailure(envelope["error"])
        return str(envelope["body"])

    def count_tokens(self, messages: list[dict[str, str]], *, timeout: float) -> int:
        # Use the same server template and non-thinking setting as generation.
        import time

        start = time.monotonic()
        try:
            rendered = json.loads(
                self.request(
                    "/apply-template",
                    {"messages": messages, "chat_template_kwargs": {"enable_thinking": False}},
                    timeout=timeout,
                )
            )["prompt"]
            if not isinstance(rendered, str):
                raise ValueError
            remaining = timeout - (time.monotonic() - start)
            if remaining <= 0:
                raise ModelFailure("MODEL_TIMEOUT")
            tokens = json.loads(
                self.request(
                    "/tokenize",
                    {"content": rendered, "add_special": True, "parse_special": True},
                    timeout=remaining,
                )
            )["tokens"]
            if not isinstance(tokens, list) or any(type(token) is not int for token in tokens):
                raise ValueError
            return len(tokens)
        except (KeyError, ValueError, TypeError) as exc:
            raise ModelFailure("INVALID_TOKENIZER_RESPONSE") from exc

    def complete(
        self,
        messages: list[dict[str, str]],
        schema: dict[str, Any],
        *,
        max_tokens: int,
        timeout: float,
    ) -> str:
        return self.request(
            "/v1/chat/completions",
            {
                "model": self.config.model,
                "messages": messages,
                "response_format": {"type": "json_object", "schema": schema},
                "chat_template_kwargs": {"enable_thinking": False},
                "temperature": self.config.temperature,
                "top_p": self.config.top_p,
                "top_k": self.config.top_k,
                "min_p": 0,
                "seed": self.config.seed,
                "max_tokens": max_tokens,
                "stream": False,
                "cache_prompt": False,
            },
            timeout=timeout,
        )
