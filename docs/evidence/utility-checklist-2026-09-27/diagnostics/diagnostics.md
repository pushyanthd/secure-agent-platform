# Runtime diagnostics

Mode: `fresh_local_inference`; scheduled episodes: 32.

Saved model calls: 117; usage known: 116; usage unknown: 1.
Reported generated tokens: 3895; reserved allowance for unknown usage: 768.
Episodes with unknown duration: 0 (excluded from timing distributions).

| Profile | Episodes with denial | Task success among them | Later allowed action and task success |
|---|---:|---:|---:|
| defended | 18 | 5 | 4 |

| Profile / tool | Proposals | Allowed | Denied | Awaiting approval | Simulated reviews |
|---|---:|---:|---:|---:|---:|
| defended / documents.read | 39 | 39 | 0 | 0 | 0 |
| defended / documents.search | 1 | 0 | 1 | 0 | 0 |
| defended / tickets.create | 26 | 6 | 20 | 0 | 0 |
| defended / tickets.list | 7 | 7 | 0 | 0 | 0 |
| defended / tickets.update | 5 | 5 | 0 | 0 | 0 |
| defended / shares.request | 7 | 5 | 2 | 0 | 7 |

| Observed quantity | N | Min | Median | P95 | Max |
|---|---:|---:|---:|---:|---:|
| reported_prompt_tokens | 116 | 1697 | 1947.0 | 3033.75 | 3401 |
| reported_completion_tokens | 116 | 10 | 30.5 | 54.75 | 131 |
| reported_context_headroom_tokens | 116 | 4750 | 6215.0 | 6454.0 | 6468 |
| model_call_seconds | 116 | 23.36 | 30.207 | 46.712 | 55.474 |
| episode_seconds | 32 | 52.749 | 97.806 | 273.325 | 300.013 |

## Limits

- Server-reported token usage is not independent metering or tokenizer admission evidence.
- Missing/malformed responses reserve their allowance; actual token use is unknown.
- Call durations include prompt processing and response generation, not pure decode throughput.
- Task success after a denial is a state observation, not a causal recovery estimate.
- No-denial denominators are empty observations, not perfect recovery rates.
- Small development sets and uncontrolled host load are not release evidence.
- Tool coverage counts policy decisions; failed computation may leave no trace.
