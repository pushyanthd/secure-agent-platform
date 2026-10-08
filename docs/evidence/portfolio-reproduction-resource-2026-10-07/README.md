# Fresh reproduction after resource completion

All checks passed in a fresh source snapshot, Python environment and dependency
cache on the configured Ubuntu/WSL PC. This is same-author local reproduction;
independent external review remains open. Network access installed locked
dependencies, and verification made zero fresh-model inference calls.

- All **800 Python tests**, lint, formatting and strict types passed.
- The original release corpus validated with unchanged templates and graders.
- Authored replay and durable-worker demos passed with zero model trials.
- All eight portable PC inference publications independently regraded: **388
  outcomes**, retaining every failed task and noncompleted outcome.

[Source hashes and exact commands/status](result.json) | [Check logs](logs/contracts.log).
The snapshot includes the resource comparison publication and its exact bytes.
This reproduction publication and later editorial cross-links are outside that
snapshot; they do not change the checked Python implementation or grading state.

This check does not rerun inference, Docker containment or browser scenarios.
Separate measurements retain their documented scopes: [24 PC Docker probes](../pc-sandbox-2026-10-07/README.md),
sixteen browser scenarios and the [reviewed fixture recording](../portfolio-walkthrough-2026-10-07/README.md).
The earlier [766-test/272-outcome](../portfolio-reproduction-broad-2026-10-07/README.md)
and [735-test/124-outcome](../portfolio-reproduction-2026-10-07/README.md)
snapshots remain historical evidence.

```sh
make portfolio-check
```

Passing reproduction does not pass a model selection rule or the original
release gate, which remains FAIL. All commands, exit codes, logs, source hashes
and scope limits are retained.
