# Runtime diagnostics

Mode: `fresh_local_inference`; scheduled episodes: 20.

Saved model calls: 64; usage known: 64; usage unknown: 0.
Reported generated tokens: 2091; reserved allowance for unknown usage: 0.
Episodes with unknown duration: 0 (excluded from timing distributions).

| Profile | Episodes with denial | Task success among them | Later allowed action and task success |
|---|---:|---:|---:|
| defended | 8 | 8 | 3 |

| Profile / tool | Proposals | Allowed | Denied | Awaiting approval | Simulated reviews |
|---|---:|---:|---:|---:|---:|
| defended / documents.read | 25 | 22 | 3 | 0 | 0 |
| defended / documents.search | 0 | 0 | 0 | 0 | 0 |
| defended / tickets.create | 19 | 14 | 5 | 0 | 5 |
| defended / tickets.list | 0 | 0 | 0 | 0 | 0 |
| defended / tickets.update | 0 | 0 | 0 | 0 | 0 |
| defended / shares.request | 0 | 0 | 0 | 0 | 0 |

| Observed quantity | N | Min | Median | P95 | Max |
|---|---:|---:|---:|---:|---:|
| reported_prompt_tokens | 64 | 1647 | 1735.0 | 2056.0 | 2156 |
| reported_completion_tokens | 64 | 11 | 26.0 | 67.7 | 75 |
| reported_context_headroom_tokens | 64 | 5989 | 6415.0 | 6520.55 | 6524 |
| model_call_seconds | 64 | 0.489 | 0.636 | 0.917 | 0.978 |
| episode_seconds | 20 | 1.749 | 3.361 | 4.582 | 4.626 |

## Limits

- Server-reported token usage is not independent metering or tokenizer admission evidence.
- Missing/malformed responses reserve their allowance; actual token use is unknown.
- Call durations include prompt processing and response generation, not pure decode throughput.
- Task success after a denial is a state observation, not a causal recovery estimate.
- No-denial denominators are empty observations, not perfect recovery rates.
- Small development sets and uncontrolled host load are not release evidence.
- Tool coverage counts policy decisions; failed computation may leave no trace.
