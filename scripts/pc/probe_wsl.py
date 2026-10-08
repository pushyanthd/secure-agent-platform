"""Verify the PC profile and perform one real structured generation from Ubuntu."""

import json
from pathlib import Path

from agentguard.live import atomic_json, prepare_local_model
from agentguard.model import parse_reply


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    model, profile, server = prepare_local_model(root, root / "artifacts/pc-wsl/model-profile.json")
    if "preflight_error" in server:
        raise SystemExit(f"Start the Windows model server: {server['preflight_error']}")
    messages = [{"role": "user", "content": "Return true in the ok field."}]
    tokens = model.count_tokens(messages, timeout=20)
    schema = {
        "type": "object",
        "properties": {"ok": {"type": "boolean"}},
        "required": ["ok"],
        "additionalProperties": False,
    }
    reply = parse_reply(model.complete(messages, schema, max_tokens=32, timeout=60))
    if json.loads(reply.content) != {"ok": True}:
        raise SystemExit("Structured-generation probe returned an unexpected result")
    atomic_json(
        root / "artifacts/pc-wsl/preflight.json",
        {
            "mode": "fresh_same_pc_inference_probe",
            "release_evidence": False,
            "profile": profile,
            "server": server,
            "prompt_tokens": tokens,
            "completion_tokens": reply.completion_tokens,
            "content": json.loads(reply.content),
        },
    )
    print(
        f"PASS: WSL -> Windows CUDA, {model.config.model}, {reply.completion_tokens} output tokens"
    )


if __name__ == "__main__":
    main()
