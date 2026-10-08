# Six-workflow corpus expansion: authored Docker evidence

**90 authored episodes, zero model trials, no held-out release claim.** All
scheduled episodes completed through the fixed Docker tool container. The command
exited 1 because seven defended attacks succeeded. Those results are retained;
there were no infrastructure failures or missing episodes.

| Profile | Clean tasks | Tasks under attack | Observed attacker wins |
|---|---:|---:|---:|
| Baseline | 6/6 | 0/24 | 24/24 |
| Prompt-only | 6/6 | 0/24 | 24/24 |
| Defended | 6/6 | 17/24 | 7/24 |

These scripts intentionally propose each attack and attempt the legitimate task.
They do not measure whether a model obeys an injection, recovers from a denial, or
benefits from a hardened prompt. Baseline and prompt-only execute the same authored
proposals. All **55 failed task grades** remain in the report.

Open the [offline viewer](analysis/explorer.html), [paired analysis](analysis/analysis.md),
[runtime diagnostics](diagnostics/diagnostics.md), [raw report](run/report.json),
or [failure review](failure-review.json).

## What the defended failures show

Four attacks mutate a protected sibling ticket inside an otherwise authorized
internal project. The gateway checks project scope, ACLs, and versions; it does
not enforce a task-specific ticket allowlist for ordinary internal updates.
Three attacks disclose the confidential marker in final response text, outside
the tool gateway: one plaintext, one canonical base64, and one lowercase hex.
Sensitive tool effects can be correctly reviewed while a final response still leaks.

These are reachable paths under the current contracts, not universal bypasses or
estimated model attack rates. The independent grader checks stored state and
output, and the smoke command remains nonzero for these wins. The
[disclosure screenshot](defended-response-disclosure.png) shows the failing task,
the authored response, and the encoded-canary predicate together.

The [full corpus contract](../../development-corpus.md) documents the six workflows,
their development ancestors, attack capabilities, exact matching rules, and
remaining split/freeze work. The combined catalogue reaches twenty tasks and 174
episodes; its deterministic regression passed all 20 defended clean tasks and
retained the same seven wins among 38 attacked inputs. This is separate from the
older 84-episode **live** study, whose results and graders are unchanged.

## Reproduction and integrity

```sh
uv run --locked agentguard eval-suite --suite scenarios/dev/expansion-v1.json \
  --sandbox-manifest artifacts/sandbox/manifest.json
# Expected exit 1 after completing all 90 episodes; inspect the saved report.

uv run --locked agentguard eval-analyze \
  docs/evidence/development-expansion-2026-09-24/run \
  --output artifacts/analyses/expansion-review
```

[Verification](verification.json) records 402 passing Python tests, type/lint/format
checks, 13 passing Chrome scenarios, and the full-catalogue regression. Every one
of the 90 published grades was also recalculated against the original local
database and matched its exported result. [Browser checks](browser-checks.json)
verify the selected disclosure and grade in the published viewer, with no page
errors or HTTP requests.

[Publication provenance](publication.json) lists byte-identical copied files and
the excluded SQLite backup. Approval nonces and the working database stay in
ignored local artifacts. The original checksum manifest is retained separately;
the published run has a checksum manifest for its copied subset. Source/fixture
snapshots, episode identities, model-call records (empty), and session history
are preserved. Sandbox sources and their image manifest are included. Checksums
detect inconsistency, not forgery by the host owner.

Grader v4's canonical encoding matches are opt-in and bounded in scope. This
publication does not detect arbitrary encodings or semantic leakage, provide
fresh-model effectiveness results, or pass a release-security gate.
