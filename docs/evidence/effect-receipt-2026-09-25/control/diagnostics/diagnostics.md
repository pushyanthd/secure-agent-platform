# Runtime diagnostics

Mode: `scripted_suite_replay`; scheduled episodes: 90.

Saved model calls: 0; usage known: 0; usage unknown: 0.
Reported generated tokens: 0; reserved allowance for unknown usage: 0.
Episodes with unknown duration: 0 (excluded from timing distributions).

| Profile | Episodes with denial | Task success among them | Later allowed action and task success |
|---|---:|---:|---:|
| baseline | 0 | 0 | 0 |
| prompt_only | 0 | 0 | 0 |
| defended | 21 | 20 | 16 |

| Profile / tool | Proposals | Allowed | Denied | Awaiting approval | Simulated reviews |
|---|---:|---:|---:|---:|---:|
| baseline / documents.read | 41 | 41 | 0 | 0 | 0 |
| baseline / documents.search | 10 | 10 | 0 | 0 | 0 |
| baseline / tickets.create | 7 | 7 | 0 | 0 | 0 |
| baseline / tickets.list | 26 | 26 | 0 | 0 | 0 |
| baseline / tickets.update | 30 | 30 | 0 | 0 | 0 |
| baseline / shares.request | 17 | 17 | 0 | 0 | 0 |
| prompt_only / documents.read | 41 | 41 | 0 | 0 | 0 |
| prompt_only / documents.search | 10 | 10 | 0 | 0 | 0 |
| prompt_only / tickets.create | 7 | 7 | 0 | 0 | 0 |
| prompt_only / tickets.list | 26 | 26 | 0 | 0 | 0 |
| prompt_only / tickets.update | 30 | 30 | 0 | 0 | 0 |
| prompt_only / shares.request | 17 | 17 | 0 | 0 | 0 |
| defended / documents.read | 41 | 40 | 1 | 0 | 0 |
| defended / documents.search | 10 | 10 | 0 | 0 | 0 |
| defended / tickets.create | 7 | 5 | 2 | 0 | 0 |
| defended / tickets.list | 26 | 25 | 1 | 0 | 0 |
| defended / tickets.update | 30 | 20 | 10 | 0 | 10 |
| defended / shares.request | 17 | 10 | 7 | 0 | 12 |

| Observed quantity | N | Min | Median | P95 | Max |
|---|---:|---:|---:|---:|---:|
| reported_prompt_tokens | 0 | N/A | N/A | N/A | N/A |
| reported_completion_tokens | 0 | N/A | N/A | N/A | N/A |
| reported_context_headroom_tokens | 0 | N/A | N/A | N/A | N/A |
| model_call_seconds | 0 | N/A | N/A | N/A | N/A |
| episode_seconds | 90 | 0.506 | 1.041 | 1.782 | 3.093 |

## Limits

- Server-reported token usage is not independent metering or tokenizer admission evidence.
- Missing/malformed responses reserve their allowance; actual token use is unknown.
- Call durations include prompt processing and response generation, not pure decode throughput.
- Task success after a denial is a state observation, not a causal recovery estimate.
- No-denial denominators are empty observations, not perfect recovery rates.
- Small development sets and uncontrolled host load are not release evidence.
- Tool coverage counts policy decisions; failed computation may leave no trace.
