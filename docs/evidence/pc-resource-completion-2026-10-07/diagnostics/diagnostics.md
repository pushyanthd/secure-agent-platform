# Runtime diagnostics

Mode: `fresh_local_inference`; scheduled episodes: 116.

Saved model calls: 495; usage known: 495; usage unknown: 0.
Reported generated tokens: 16193; reserved allowance for unknown usage: 0.
Episodes with unknown duration: 0 (excluded from timing distributions).

| Profile | Episodes with denial | Task success among them | Later allowed action and task success |
|---|---:|---:|---:|
| defended | 27 | 27 | 16 |

| Profile / tool | Proposals | Allowed | Denied | Awaiting approval | Simulated reviews |
|---|---:|---:|---:|---:|---:|
| defended / documents.read | 151 | 144 | 7 | 0 | 0 |
| defended / documents.search | 28 | 28 | 0 | 0 | 0 |
| defended / tickets.create | 49 | 42 | 7 | 0 | 10 |
| defended / tickets.list | 62 | 62 | 0 | 0 | 0 |
| defended / tickets.update | 57 | 44 | 13 | 0 | 20 |
| defended / shares.request | 24 | 24 | 0 | 0 | 24 |

| Observed quantity | N | Min | Median | P95 | Max |
|---|---:|---:|---:|---:|---:|
| reported_prompt_tokens | 495 | 1690 | 1917.0 | 2346.0 | 2515 |
| reported_completion_tokens | 495 | 11 | 25.0 | 65.0 | 142 |
| reported_context_headroom_tokens | 495 | 5624 | 6252.0 | 6457.0 | 6481 |
| model_call_seconds | 495 | 0.498 | 0.631 | 0.962 | 1.563 |
| episode_seconds | 116 | 1.764 | 4.47 | 7.239 | 7.985 |

## Limits

- Server-reported token usage is not independent metering or tokenizer admission evidence.
- Missing/malformed responses reserve their allowance; actual token use is unknown.
- Call durations include prompt processing and response generation, not pure decode throughput.
- Task success after a denial is a state observation, not a causal recovery estimate.
- No-denial denominators are empty observations, not perfect recovery rates.
- Small development sets and uncontrolled host load are not release evidence.
- Tool coverage counts policy decisions; failed computation may leave no trace.
