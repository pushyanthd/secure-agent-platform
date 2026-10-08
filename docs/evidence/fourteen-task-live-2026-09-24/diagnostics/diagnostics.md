# Runtime diagnostics

Mode: `fresh_local_inference`; scheduled episodes: 84.

Saved model calls: 275; usage known: 275; usage unknown: 0.
Reported generated tokens: 9484; reserved allowance for unknown usage: 0.
Episodes with unknown duration: 0 (excluded from timing distributions).

| Profile | Episodes with denial | Task success among them | Later allowed action and task success |
|---|---:|---:|---:|
| baseline | 2 | 2 | 0 |
| prompt_only | 3 | 3 | 0 |
| defended | 9 | 8 | 1 |

| Profile / tool | Proposals | Allowed | Denied | Awaiting approval | Simulated reviews |
|---|---:|---:|---:|---:|---:|
| baseline / documents.read | 34 | 32 | 2 | 0 | 0 |
| baseline / documents.search | 4 | 4 | 0 | 0 | 0 |
| baseline / tickets.create | 16 | 16 | 0 | 0 | 0 |
| baseline / tickets.list | 2 | 2 | 0 | 0 | 0 |
| baseline / tickets.update | 2 | 2 | 0 | 0 | 0 |
| baseline / shares.request | 4 | 4 | 0 | 0 | 0 |
| prompt_only / documents.read | 36 | 34 | 2 | 0 | 0 |
| prompt_only / documents.search | 4 | 4 | 0 | 0 | 0 |
| prompt_only / tickets.create | 18 | 17 | 1 | 0 | 0 |
| prompt_only / tickets.list | 2 | 2 | 0 | 0 | 0 |
| prompt_only / tickets.update | 2 | 2 | 0 | 0 | 0 |
| prompt_only / shares.request | 3 | 3 | 0 | 0 | 0 |
| defended / documents.read | 34 | 30 | 4 | 0 | 0 |
| defended / documents.search | 4 | 4 | 0 | 0 | 0 |
| defended / tickets.create | 20 | 15 | 5 | 0 | 4 |
| defended / tickets.list | 2 | 2 | 0 | 0 | 0 |
| defended / tickets.update | 2 | 2 | 0 | 0 | 0 |
| defended / shares.request | 2 | 2 | 0 | 0 | 2 |

| Observed quantity | N | Min | Median | P95 | Max |
|---|---:|---:|---:|---:|---:|
| reported_prompt_tokens | 275 | 1557 | 1706.0 | 1925.3 | 2140 |
| reported_completion_tokens | 275 | 11 | 29.0 | 68.0 | 110 |
| reported_context_headroom_tokens | 275 | 5970 | 6451.0 | 6602.0 | 6614 |
| model_call_seconds | 275 | 19.907 | 27.313 | 43.933 | 53.126 |
| episode_seconds | 84 | 65.175 | 98.696 | 134.938 | 178.939 |

## Limits

- Server-reported token usage is not independent metering or tokenizer admission evidence.
- Missing/malformed responses reserve their allowance; actual token use is unknown.
- Call durations include prompt processing and response generation, not pure decode throughput.
- Task success after a denial is a state observation, not a causal recovery estimate.
- No-denial denominators are empty observations, not perfect recovery rates.
- Small development sets and uncontrolled host load are not release evidence.
- Tool coverage counts policy decisions; failed computation may leave no trace.
