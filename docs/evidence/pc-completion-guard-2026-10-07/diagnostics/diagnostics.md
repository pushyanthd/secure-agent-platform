# Runtime diagnostics

Mode: `fresh_local_inference`; scheduled episodes: 8.

Saved model calls: 25; usage known: 25; usage unknown: 0.
Reported generated tokens: 1564; reserved allowance for unknown usage: 0.
Episodes with unknown duration: 0 (excluded from timing distributions).

| Profile | Episodes with denial | Task success among them | Later allowed action and task success |
|---|---:|---:|---:|
| defended | 0 | 0 | 0 |

| Profile / tool | Proposals | Allowed | Denied | Awaiting approval | Simulated reviews |
|---|---:|---:|---:|---:|---:|
| defended / documents.read | 8 | 8 | 0 | 0 | 0 |
| defended / documents.search | 0 | 0 | 0 | 0 | 0 |
| defended / tickets.create | 7 | 7 | 0 | 0 | 0 |
| defended / tickets.list | 0 | 0 | 0 | 0 | 0 |
| defended / tickets.update | 0 | 0 | 0 | 0 | 0 |
| defended / shares.request | 0 | 0 | 0 | 0 | 0 |

| Observed quantity | N | Min | Median | P95 | Max |
|---|---:|---:|---:|---:|---:|
| reported_prompt_tokens | 25 | 1861 | 2036.0 | 2576.4 | 2746 |
| reported_completion_tokens | 25 | 12 | 32.0 | 151.0 | 567 |
| reported_context_headroom_tokens | 25 | 5351 | 6144.0 | 6304.0 | 6304 |
| model_call_seconds | 25 | 0.541 | 0.687 | 1.594 | 4.669 |
| episode_seconds | 8 | 3.031 | 3.34 | 7.427 | 8.771 |

## Limits

- Server-reported token usage is not independent metering or tokenizer admission evidence.
- Missing/malformed responses reserve their allowance; actual token use is unknown.
- Call durations include prompt processing and response generation, not pure decode throughput.
- Task success after a denial is a state observation, not a causal recovery estimate.
- No-denial denominators are empty observations, not perfect recovery rates.
- Small development sets and uncontrolled host load are not release evidence.
- Tool coverage counts policy decisions; failed computation may leave no trace.
