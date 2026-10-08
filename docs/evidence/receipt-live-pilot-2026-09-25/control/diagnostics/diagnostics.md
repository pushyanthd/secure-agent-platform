# Runtime diagnostics

Mode: `fresh_local_inference`; scheduled episodes: 5.

Saved model calls: 21; usage known: 21; usage unknown: 0.
Reported generated tokens: 613; reserved allowance for unknown usage: 0.
Episodes with unknown duration: 0 (excluded from timing distributions).

| Profile | Episodes with denial | Task success among them | Later allowed action and task success |
|---|---:|---:|---:|
| defended | 1 | 0 | 0 |

| Profile / tool | Proposals | Allowed | Denied | Awaiting approval | Simulated reviews |
|---|---:|---:|---:|---:|---:|
| defended / documents.read | 5 | 5 | 0 | 0 | 0 |
| defended / documents.search | 0 | 0 | 0 | 0 | 0 |
| defended / tickets.create | 1 | 0 | 1 | 0 | 0 |
| defended / tickets.list | 5 | 5 | 0 | 0 | 0 |
| defended / tickets.update | 5 | 5 | 0 | 0 | 5 |
| defended / shares.request | 0 | 0 | 0 | 0 | 0 |

| Observed quantity | N | Min | Median | P95 | Max |
|---|---:|---:|---:|---:|---:|
| reported_prompt_tokens | 21 | 1692 | 1849.0 | 2243.0 | 2327 |
| reported_completion_tokens | 21 | 13 | 25.0 | 50.0 | 68 |
| reported_context_headroom_tokens | 21 | 5852 | 6293.0 | 6479.0 | 6479 |
| model_call_seconds | 21 | 21.538 | 28.084 | 39.816 | 46.218 |
| episode_seconds | 5 | 106.694 | 114.119 | 154.588 | 157.931 |

## Limits

- Server-reported token usage is not independent metering or tokenizer admission evidence.
- Missing/malformed responses reserve their allowance; actual token use is unknown.
- Call durations include prompt processing and response generation, not pure decode throughput.
- Task success after a denial is a state observation, not a causal recovery estimate.
- No-denial denominators are empty observations, not perfect recovery rates.
- Small development sets and uncontrolled host load are not release evidence.
- Tool coverage counts policy decisions; failed computation may leave no trace.
