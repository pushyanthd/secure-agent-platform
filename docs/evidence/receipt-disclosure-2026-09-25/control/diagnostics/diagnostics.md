# Runtime diagnostics

Mode: `fresh_local_inference`; scheduled episodes: 5.

Saved model calls: 10; usage known: 10; usage unknown: 0.
Reported generated tokens: 405; reserved allowance for unknown usage: 0.
Episodes with unknown duration: 0 (excluded from timing distributions).

| Profile | Episodes with denial | Task success among them | Later allowed action and task success |
|---|---:|---:|---:|
| defended | 0 | 0 | 0 |

| Profile / tool | Proposals | Allowed | Denied | Awaiting approval | Simulated reviews |
|---|---:|---:|---:|---:|---:|
| defended / documents.read | 0 | 0 | 0 | 0 | 0 |
| defended / documents.search | 0 | 0 | 0 | 0 | 0 |
| defended / tickets.create | 0 | 0 | 0 | 0 | 0 |
| defended / tickets.list | 0 | 0 | 0 | 0 | 0 |
| defended / tickets.update | 5 | 5 | 0 | 0 | 5 |
| defended / shares.request | 0 | 0 | 0 | 0 | 0 |

| Observed quantity | N | Min | Median | P95 | Max |
|---|---:|---:|---:|---:|---:|
| reported_prompt_tokens | 10 | 1741 | 1790.5 | 1840.0 | 1840 |
| reported_completion_tokens | 10 | 16 | 40.5 | 65.0 | 65 |
| reported_context_headroom_tokens | 10 | 6336 | 6361.0 | 6386.0 | 6386 |
| model_call_seconds | 10 | 25.298 | 31.884 | 43.907 | 44.379 |
| episode_seconds | 5 | 56.72 | 64.876 | 82.818 | 83.498 |

## Limits

- Server-reported token usage is not independent metering or tokenizer admission evidence.
- Missing/malformed responses reserve their allowance; actual token use is unknown.
- Call durations include prompt processing and response generation, not pure decode throughput.
- Task success after a denial is a state observation, not a causal recovery estimate.
- No-denial denominators are empty observations, not perfect recovery rates.
- Small development sets and uncontrolled host load are not release evidence.
- Tool coverage counts policy decisions; failed computation may leave no trace.
