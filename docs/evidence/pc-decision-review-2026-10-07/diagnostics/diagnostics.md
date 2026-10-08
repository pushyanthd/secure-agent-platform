# Runtime diagnostics

Mode: `fresh_local_inference`; scheduled episodes: 32.

Saved model calls: 153; usage known: 153; usage unknown: 0.
Reported generated tokens: 5866; reserved allowance for unknown usage: 0.
Episodes with unknown duration: 0 (excluded from timing distributions).

| Profile | Episodes with denial | Task success among them | Later allowed action and task success |
|---|---:|---:|---:|
| defended | 3 | 2 | 2 |

| Profile / tool | Proposals | Allowed | Denied | Awaiting approval | Simulated reviews |
|---|---:|---:|---:|---:|---:|
| defended / documents.read | 34 | 34 | 0 | 0 | 0 |
| defended / documents.search | 0 | 0 | 0 | 0 | 0 |
| defended / tickets.create | 9 | 7 | 2 | 0 | 0 |
| defended / tickets.list | 8 | 8 | 0 | 0 | 0 |
| defended / tickets.update | 6 | 6 | 0 | 0 | 0 |
| defended / shares.request | 5 | 4 | 1 | 0 | 5 |

| Observed quantity | N | Min | Median | P95 | Max |
|---|---:|---:|---:|---:|---:|
| reported_prompt_tokens | 153 | 1848 | 2157.0 | 4208.4 | 4882 |
| reported_completion_tokens | 153 | 13 | 30.0 | 87.0 | 130 |
| reported_context_headroom_tokens | 153 | 3223 | 5990.0 | 6308.6 | 6317 |
| model_call_seconds | 153 | 0.537 | 0.758 | 1.409 | 1.643 |
| episode_seconds | 32 | 1.851 | 4.759 | 10.72 | 11.54 |

## Limits

- Server-reported token usage is not independent metering or tokenizer admission evidence.
- Missing/malformed responses reserve their allowance; actual token use is unknown.
- Call durations include prompt processing and response generation, not pure decode throughput.
- Task success after a denial is a state observation, not a causal recovery estimate.
- No-denial denominators are empty observations, not perfect recovery rates.
- Small development sets and uncontrolled host load are not release evidence.
- Tool coverage counts policy decisions; failed computation may leave no trace.
