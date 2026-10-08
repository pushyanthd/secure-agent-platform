# Runtime diagnostics

Mode: `fresh_local_inference`; scheduled episodes: 400.

Saved model calls: 1394; usage known: 1391; usage unknown: 3.
Reported generated tokens: 46293; reserved allowance for unknown usage: 2304.
Episodes with unknown duration: 1 (excluded from timing distributions).

| Profile | Episodes with denial | Task success among them | Later allowed action and task success |
|---|---:|---:|---:|
| baseline | 0 | 0 | 0 |
| defended | 125 | 6 | 6 |

| Profile / tool | Proposals | Allowed | Denied | Awaiting approval | Simulated reviews |
|---|---:|---:|---:|---:|---:|
| baseline / documents.read | 222 | 222 | 0 | 0 | 0 |
| baseline / documents.search | 58 | 58 | 0 | 0 | 0 |
| baseline / tickets.create | 72 | 72 | 0 | 0 | 0 |
| baseline / tickets.list | 24 | 24 | 0 | 0 | 0 |
| baseline / tickets.update | 36 | 36 | 0 | 0 | 0 |
| baseline / shares.request | 65 | 65 | 0 | 0 | 0 |
| defended / documents.read | 248 | 214 | 34 | 0 | 0 |
| defended / documents.search | 50 | 42 | 8 | 0 | 0 |
| defended / tickets.create | 78 | 34 | 44 | 0 | 0 |
| defended / tickets.list | 32 | 32 | 0 | 0 | 0 |
| defended / tickets.update | 34 | 34 | 0 | 0 | 0 |
| defended / shares.request | 75 | 10 | 65 | 0 | 26 |

| Observed quantity | N | Min | Median | P95 | Max |
|---|---:|---:|---:|---:|---:|
| reported_prompt_tokens | 1391 | 1641 | 1862.0 | 2405.5 | 3564 |
| reported_completion_tokens | 1391 | 10 | 31.0 | 60.0 | 160 |
| reported_context_headroom_tokens | 1391 | 4555 | 6299.0 | 6510.0 | 6526 |
| model_call_seconds | 1391 | 20.589 | 27.121 | 39.527 | 64.732 |
| episode_seconds | 399 | 43.478 | 91.55 | 171.94 | 300.013 |

## Limits

- Server-reported token usage is not independent metering or tokenizer admission evidence.
- Missing/malformed responses reserve their allowance; actual token use is unknown.
- Call durations include prompt processing and response generation, not pure decode throughput.
- Task success after a denial is a state observation, not a causal recovery estimate.
- No-denial denominators are empty observations, not perfect recovery rates.
- Small development sets and uncontrolled host load are not release evidence.
- Tool coverage counts policy decisions; failed computation may leave no trace.
