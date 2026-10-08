# Runtime diagnostics

Mode: `fresh_local_inference`; scheduled episodes: 32.

Saved model calls: 105; usage known: 105; usage unknown: 0.
Reported generated tokens: 3714; reserved allowance for unknown usage: 0.
Episodes with unknown duration: 0 (excluded from timing distributions).

| Profile | Episodes with denial | Task success among them | Later allowed action and task success |
|---|---:|---:|---:|
| defended | 6 | 2 | 2 |

| Profile / tool | Proposals | Allowed | Denied | Awaiting approval | Simulated reviews |
|---|---:|---:|---:|---:|---:|
| defended / documents.read | 34 | 34 | 0 | 0 | 0 |
| defended / documents.search | 0 | 0 | 0 | 0 | 0 |
| defended / tickets.create | 11 | 6 | 5 | 0 | 0 |
| defended / tickets.list | 8 | 8 | 0 | 0 | 0 |
| defended / tickets.update | 8 | 8 | 0 | 0 | 0 |
| defended / shares.request | 8 | 7 | 1 | 0 | 8 |

| Observed quantity | N | Min | Median | P95 | Max |
|---|---:|---:|---:|---:|---:|
| reported_prompt_tokens | 105 | 1848 | 2039.0 | 2671.0 | 2745 |
| reported_completion_tokens | 105 | 13 | 28.0 | 71.8 | 160 |
| reported_context_headroom_tokens | 105 | 5287 | 6120.0 | 6317.0 | 6317 |
| model_call_seconds | 105 | 0.536 | 0.685 | 1.028 | 1.765 |
| episode_seconds | 32 | 1.861 | 3.391 | 6.138 | 6.74 |

## Limits

- Server-reported token usage is not independent metering or tokenizer admission evidence.
- Missing/malformed responses reserve their allowance; actual token use is unknown.
- Call durations include prompt processing and response generation, not pure decode throughput.
- Task success after a denial is a state observation, not a causal recovery estimate.
- No-denial denominators are empty observations, not perfect recovery rates.
- Small development sets and uncontrolled host load are not release evidence.
- Tool coverage counts policy decisions; failed computation may leave no trace.
