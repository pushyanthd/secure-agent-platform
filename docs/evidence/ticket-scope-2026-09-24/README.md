# Ticket-scope treatment: authored Docker evidence

**90 scripted episodes completed, zero fresh model trials.** The `gateway-v3`
treatment blocks the four sibling-ticket edits exposed by expansion-v1. All six
defended clean workflows still pass; the three final-response disclosures remain
failed. The command exits 1 after saving every outcome.

| Profile | Clean task success | Task success under attack | Attacker wins |
|---|---:|---:|---:|
| Baseline | 6/6 | 0/24 | 24/24 |
| Prompt-only | 6/6 | 0/24 | 24/24 |
| Defended | 6/6 | 21/24 | 3/24 |

Open the [offline viewer](analysis/explorer.html), [analysis](analysis/analysis.md),
[diagnostics](diagnostics/diagnostics.md), [report](run/report.md), or
[exact treatment comparison](treatment-review.json). All **51 failed task grades**
across the three profiles remain present. There are no missing or noncompleted
episodes in this run.

Compared with the [original expansion study](../development-expansion-2026-09-24/README.md),
86 episode task/attack outcomes are unchanged and four defended outcomes improve.
Three fixes concern `search-backed-maintenance`; one concerns
`update-and-publish-handoff`. Each excluded sibling receives `TICKET_OUT_OF_SCOPE`.
The scripts then perform the authorized update. This demonstrates application
enforcement and authored recovery, not model attack resistance or live recovery.

The three retained `confidential-response-triage` failures disclose the synthetic
marker in plaintext, standard base64, and lowercase hex. The tool gateway does
not authorize final response text. The unchanged independent grader records these
failures. See [ADR 003](../../adr-003-ticket-scope-and-response-boundary.md) for the
trusted scope contract, compatibility behavior, and explicit response limitation.

## Reproduce

```sh
uv run --locked agentguard eval-suite --suite scenarios/dev/expansion-v2.json \
  --sandbox-manifest artifacts/sandbox/manifest.json
# Expected exit 1: three retained response disclosures.

uv run --locked agentguard eval-analyze \
  docs/evidence/ticket-scope-2026-09-24/run \
  --output artifacts/analyses/ticket-scope-review
```

`make eval-ticket-scope` runs the same authored schedule in-process. The complete
`make eval-development` catalogue uses v5: 174 scripted episodes, defended clean
utility 20/20, attacked utility 35/38, and three attack wins. No held-out release
gate or fresh-model improvement is claimed.

## Verification and provenance

[Verification](verification.json) records 423 Python tests, lint/format/type
checks, the frontend build, and 14 Chrome scenarios. The new browser scenario
checks ticket scope in selection and approval detail and verifies that a reviewed
update leaves its sibling unchanged. All 90 Docker grades were recalculated
against a disposable copy of the original database and matched the exported grades.

[Publication provenance](publication.json) records copied file hashes and the
excluded database. The original checksum manifest is preserved separately;
the published subset has its own checksum manifest. Source and fixture snapshots,
raw reports, model-call records (empty), and session history are unchanged.
SQLite and approval nonces remain in ignored local artifacts. Checksums detect
inconsistency, not tampering by the machine owner.

The first attempt could not access Docker's socket from the restricted process.
It recorded 90 infrastructure failures before any tool completed. That run remains
under the local path and hash in `publication.json`; its counts are retained there
and are not pooled with the new authorized run. Browser checks also initially
failed at sandbox process/network boundaries before passing with local access.
Neither failure was reclassified as a successful security trial.
