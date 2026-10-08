# Fresh reproduction after broader development

All checks passed in a fresh source snapshot, Python environment and dependency
cache on the configured Ubuntu/WSL PC. This is same-author local reproduction,
not an independent external review. Network access installed locked dependencies;
verification then made zero fresh-model inference calls.

- All **766 Python tests**, lint, formatting and strict types passed.
- The original release corpus validated with its existing templates and graders.
- Authored replay and durable-worker demos passed with zero model trials.
- All seven portable PC inference publications independently regraded: **272
  outcomes**, including failed tasks and eleven broader noncompleted trials.

[Source hashes and exact commands/status](result.json) | [Retained logs](logs/contracts.log).
The snapshot was taken after the structured and broader studies, recording and
PC container publications. It includes their exact bytes/hashes. The reproduction
publication itself and later editorial cross-links are outside that snapshot;
they do not change the checked Python implementation or grading states.

This check does not rerun inference, Docker containment or browser scenarios.
Separate current measurements passed all sixteen browser tests and
[24 container probes](../pc-sandbox-2026-10-07/README.md); the
[reviewed recording](../portfolio-walkthrough-2026-10-07/README.md) demonstrates
fixture-mode UI behavior. Each keeps its own scope. The earlier
[735-test/124-outcome reproduction](../portfolio-reproduction-2026-10-07/README.md)
remains historical evidence, including its initial failed dependency-path attempt.

```sh
make portfolio-check
```

The command preserves previous outputs, creates a fresh source/environment/cache,
and keeps every check log and source hash under ignored artifacts. Both broader
configurations were rejected; passing reproduction does not pass a model utility
rule or the original release gate, which remains FAIL.
