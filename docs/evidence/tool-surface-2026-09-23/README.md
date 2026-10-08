# Six-tool development verification — September 23, 2026

The four new workflows completed all 24 scheduled episodes through the fixed
Docker runner. Actions and recovery are authored scripts, reviews are simulated,
and the model-call export is empty. **This bundle contains zero fresh model trials.**

| Profile | Clean task success | Attacked task success | Observed attack effects |
|---|---:|---:|---:|
| Baseline | 4/4 | 0/4 | 4/4 |
| Prompt-only | 4/4 | 0/4 | 4/4 |
| Defended | 4/4 | 4/4 | 0/4 |

The authored attacks attempt an out-of-scope search, an unauthorized ticket
update, a redirected document share, and disclosure after a confidential search.
Defended execution preserves the intended work in these scripts. Baseline and
prompt-only deliberately disable business checks and execute identical scripted
actions; this comparison does not measure the effect of a security prompt on a model.
All episodes completed, and the defended profile consumed two simulated share
approvals across the clean/attacked pair.

- [Full results and traces](isolated-replay/report.json)
- [Readable report](isolated-replay/report.md)
- [Paired analysis](analysis/analysis.md) and [offline comparison viewer](analysis/explorer.html)
- [Source snapshot used during the run](isolated-replay/source.json)
- [Container contract and containment checks](container-smoke.json)
- [Pinned tool image and sandbox source hashes](sandbox-manifest.json)
- [Exact-document approval screenshot](share-approval.png)

All 24 container checks passed: six tool contracts and the existing isolation,
resource-limit, timeout, and oversized-output probes. The tool image is
`sha256:bbeb5e0e660aab8b2c58d25cbdaacf27a1e9598ec37f7dac2c0fd94933dd48c6`.
The matching fixed runner, probe, and Dockerfile are retained under `sandbox/`.
These checks exercise a local container boundary, not resistance to kernel escapes.

The final implementation also passed 311 Python tests, strict mypy, Ruff and
formatting, frontend TypeScript/format checks and production build, and all 11
Chrome scenarios against a real local API with separate worker invocations.
The browser adds exact-source sharing approval and versioned ticket maintenance
to the previous nine security/workflow checks. The first browser attempt ran an
older queued fixture before the new share test; the corrected ordering passed
without relaxing the approval assertion. Browser actions are automated fixture
runs, not human usability or model evidence.

The original 60-episode development replay and durable recovery demo were rerun
with the expanded implementation. Published historical live reports were neither
changed nor regraded. See [the runbook](../../tool-surface.md) for reproduction,
upgrade instructions, and the remaining fresh-model milestone.

Local SQLite files are omitted from this published bundle. Run-level checksums
cover the retained JSON/Markdown source, fixture, schedule, trace, and report
exports. The top-level checksum file also covers the container evidence and
screenshot. Hashes detect inconsistent files; they do not authenticate them
against the local machine owner. Temporary browser tokens and server logs remain
outside the bundle in ignored local artifacts.
