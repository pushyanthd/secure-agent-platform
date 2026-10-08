# Runtime diagnostics

Mode: `fresh_local_inference`; scheduled episodes: 116.

Saved model calls: 624; usage known: 624; usage unknown: 0.
Reported generated tokens: 21475; reserved allowance for unknown usage: 0.
Episodes with unknown duration: 0 (excluded from timing distributions).

| Profile | Episodes with denial | Task success among them | Later allowed action and task success |
|---|---:|---:|---:|
| defended | 32 | 26 | 16 |

| Profile / tool | Proposals | Allowed | Denied | Awaiting approval | Simulated reviews |
|---|---:|---:|---:|---:|---:|
| defended / documents.read | 154 | 148 | 6 | 0 | 0 |
| defended / documents.search | 28 | 28 | 0 | 0 | 0 |
| defended / tickets.create | 48 | 42 | 6 | 0 | 9 |
| defended / tickets.list | 66 | 66 | 0 | 0 | 0 |
| defended / tickets.update | 64 | 44 | 20 | 0 | 20 |
| defended / shares.request | 24 | 24 | 0 | 0 | 24 |

| Observed quantity | N | Min | Median | P95 | Max |
|---|---:|---:|---:|---:|---:|
| reported_prompt_tokens | 624 | 1690 | 1954.0 | 2886.7 | 3462 |
| reported_completion_tokens | 624 | 11 | 27.0 | 67.0 | 146 |
| reported_context_headroom_tokens | 624 | 4717 | 6193.0 | 6468.1 | 6481 |
| model_call_seconds | 624 | 0.505 | 0.676 | 1.01 | 1.578 |
| episode_seconds | 116 | 1.813 | 5.962 | 9.396 | 9.617 |

## Limits

- Server-reported token usage is not independent metering or tokenizer admission evidence.
- Missing/malformed responses reserve their allowance; actual token use is unknown.
- Call durations include prompt processing and response generation, not pure decode throughput.
- Task success after a denial is a state observation, not a causal recovery estimate.
- No-denial denominators are empty observations, not perfect recovery rates.
- Small development sets and uncontrolled host load are not release evidence.
- Tool coverage counts policy decisions; failed computation may leave no trace.
