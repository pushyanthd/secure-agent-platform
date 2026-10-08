# Runtime diagnostics

Mode: `fresh_local_inference`; scheduled episodes: 32.

Saved model calls: 100; usage known: 100; usage unknown: 0.
Reported generated tokens: 3549; reserved allowance for unknown usage: 0.
Episodes with unknown duration: 0 (excluded from timing distributions).

| Profile | Episodes with denial | Task success among them | Later allowed action and task success |
|---|---:|---:|---:|
| defended | 7 | 2 | 1 |

| Profile / tool | Proposals | Allowed | Denied | Awaiting approval | Simulated reviews |
|---|---:|---:|---:|---:|---:|
| defended / documents.read | 38 | 38 | 0 | 0 | 0 |
| defended / documents.search | 0 | 0 | 0 | 0 | 0 |
| defended / tickets.create | 9 | 3 | 6 | 0 | 0 |
| defended / tickets.list | 7 | 7 | 0 | 0 | 0 |
| defended / tickets.update | 6 | 6 | 0 | 0 | 0 |
| defended / shares.request | 8 | 7 | 1 | 0 | 8 |

| Observed quantity | N | Min | Median | P95 | Max |
|---|---:|---:|---:|---:|---:|
| reported_prompt_tokens | 100 | 1717 | 1943.0 | 2564.6 | 2747 |
| reported_completion_tokens | 100 | 12 | 28.0 | 71.2 | 126 |
| reported_context_headroom_tokens | 100 | 5374 | 6222.0 | 6434.0 | 6448 |
| model_call_seconds | 100 | 0.519 | 0.64 | 1.018 | 1.376 |
| episode_seconds | 32 | 1.833 | 3.224 | 5.821 | 6.078 |

## Limits

- Server-reported token usage is not independent metering or tokenizer admission evidence.
- Missing/malformed responses reserve their allowance; actual token use is unknown.
- Call durations include prompt processing and response generation, not pure decode throughput.
- Task success after a denial is a state observation, not a causal recovery estimate.
- No-denial denominators are empty observations, not perfect recovery rates.
- Small development sets and uncontrolled host load are not release evidence.
- Tool coverage counts policy decisions; failed computation may leave no trace.
