# Runtime diagnostics

Mode: `fresh_local_inference`; scheduled episodes: 6.

Saved model calls: 18; usage known: 18; usage unknown: 0.
Reported generated tokens: 418; reserved allowance for unknown usage: 0.

| Profile | Episodes with denial | Task success among them | Later allowed action and task success |
|---|---:|---:|---:|
| baseline | 0 | 0 | 0 |
| prompt_only | 0 | 0 | 0 |
| defended | 0 | 0 | 0 |

| Profile / tool | Proposals | Allowed | Denied | Awaiting approval | Simulated reviews |
|---|---:|---:|---:|---:|---:|
| baseline / documents.read | 2 | 2 | 0 | 0 | 0 |
| baseline / documents.search | 2 | 2 | 0 | 0 | 0 |
| baseline / tickets.create | 0 | 0 | 0 | 0 | 0 |
| baseline / tickets.list | 0 | 0 | 0 | 0 | 0 |
| baseline / tickets.update | 0 | 0 | 0 | 0 | 0 |
| baseline / shares.request | 0 | 0 | 0 | 0 | 0 |
| prompt_only / documents.read | 2 | 2 | 0 | 0 | 0 |
| prompt_only / documents.search | 2 | 2 | 0 | 0 | 0 |
| prompt_only / tickets.create | 0 | 0 | 0 | 0 | 0 |
| prompt_only / tickets.list | 0 | 0 | 0 | 0 | 0 |
| prompt_only / tickets.update | 0 | 0 | 0 | 0 | 0 |
| prompt_only / shares.request | 0 | 0 | 0 | 0 | 0 |
| defended / documents.read | 2 | 2 | 0 | 0 | 0 |
| defended / documents.search | 2 | 2 | 0 | 0 | 0 |
| defended / tickets.create | 0 | 0 | 0 | 0 | 0 |
| defended / tickets.list | 0 | 0 | 0 | 0 | 0 |
| defended / tickets.update | 0 | 0 | 0 | 0 | 0 |
| defended / shares.request | 0 | 0 | 0 | 0 | 0 |

| Observed quantity | N | Min | Median | P95 | Max |
|---|---:|---:|---:|---:|---:|
| reported_prompt_tokens | 18 | 1569 | 1695.0 | 1856.4 | 1870 |
| reported_completion_tokens | 18 | 11 | 25.0 | 34.0 | 34 |
| reported_context_headroom_tokens | 18 | 6308 | 6463.0 | 6602.0 | 6602 |
| model_call_seconds | 18 | 35.79 | 39.123 | 41.984 | 43.004 |
| episode_seconds | 6 | 115.359 | 122.388 | 125.983 | 126.322 |

## Limits

- Server-reported token usage is not independent metering or tokenizer admission evidence.
- Missing/malformed responses reserve their allowance; actual token use is unknown.
- Call durations include prompt processing and response generation, not pure decode throughput.
- Task success after a denial is a state observation, not a causal recovery estimate.
- No-denial denominators are empty observations, not perfect recovery rates.
- Small development sets and uncontrolled host load are not release evidence.
- Tool coverage counts policy decisions; failed computation may leave no trace.
