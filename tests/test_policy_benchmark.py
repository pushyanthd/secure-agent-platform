from pathlib import Path

import pytest

from agentguard.policy_benchmark import measure_policy

SUITE = Path(__file__).resolve().parents[1] / "scenarios/dev/tools-v1.json"


def test_policy_measurement_excludes_setup_and_warmup_and_never_executes_tools(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("microbenchmark must not execute a tool")

    monkeypatch.setattr("agentguard.storage.Store.execute", forbidden)
    timestamps = iter(range(0, 200_000_000, 1_000_000))
    monkeypatch.setattr(
        "agentguard.policy_benchmark.time.perf_counter_ns", lambda: next(timestamps)
    )
    result = measure_policy(SUITE, samples=100, warmup=10)
    assert result["raw_milliseconds"] == [1.0] * 100
    assert result["milliseconds"]["p95"] == 1.0
    assert result["samples"] == sum(result["tool_counts"].values()) == 100
    assert sum(result["outcome_counts"].values()) == 100
    assert set(result["tool_counts"]) == {
        "documents.read",
        "documents.search",
        "tickets.list",
        "tickets.create",
        "tickets.update",
        "shares.request",
    }
    assert set(result["outcome_counts"]) == {"ALLOW", "DENY", "REQUIRE_APPROVAL"}
    assert result["fresh_model_trials"] == 0
    assert result["case_count"] > 0


@pytest.mark.parametrize("samples,warmup", [(99, 100), (100001, 100), (100, -1), (100, 10001)])
def test_policy_measurement_rejects_unbounded_or_too_small_samples(samples, warmup):
    with pytest.raises(ValueError):
        measure_policy(SUITE, samples=samples, warmup=warmup)
