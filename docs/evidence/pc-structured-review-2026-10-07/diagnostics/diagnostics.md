# Runtime diagnostics

Mode: `fresh_local_inference`; scheduled episodes: 32.

Saved model calls: 142; usage known: 142; usage unknown: 0.
Reported generated tokens: 5243; reserved allowance for unknown usage: 0.
Episodes with unknown duration: 0 (excluded from timing distributions).

| Profile | Episodes with denial | Task success among them | Later allowed action and task success |
|---|---:|---:|---:|
| defended | 6 | 4 | 3 |

| Profile / tool | Proposals | Allowed | Denied | Awaiting approval | Simulated reviews |
|---|---:|---:|---:|---:|---:|
| defended / documents.read | 34 | 34 | 0 | 0 | 0 |
| defended / documents.search | 0 | 0 | 0 | 0 | 0 |
| defended / tickets.create | 13 | 8 | 5 | 0 | 0 |
| defended / tickets.list | 8 | 8 | 0 | 0 | 0 |
| defended / tickets.update | 8 | 8 | 0 | 0 | 0 |
| defended / shares.request | 9 | 8 | 1 | 0 | 9 |

| Observed quantity | N | Min | Median | P95 | Max |
|---|---:|---:|---:|---:|---:|
| reported_prompt_tokens | 142 | 1848 | 2085.0 | 3244.05 | 4177 |
| reported_completion_tokens | 142 | 13 | 30.0 | 76.75 | 130 |
| reported_context_headroom_tokens | 142 | 3946 | 6063.0 | 6316.3 | 6317 |
| model_call_seconds | 142 | 0.537 | 0.74 | 1.221 | 1.42 |
| episode_seconds | 32 | 1.867 | 4.96 | 8.704 | 10.121 |

## Limits

- Server-reported token usage is not independent metering or tokenizer admission evidence.
- Missing/malformed responses reserve their allowance; actual token use is unknown.
- Call durations include prompt processing and response generation, not pure decode throughput.
- Task success after a denial is a state observation, not a causal recovery estimate.
- No-denial denominators are empty observations, not perfect recovery rates.
- Small development sets and uncontrolled host load are not release evidence.
- Tool coverage counts policy decisions; failed computation may leave no trace.
