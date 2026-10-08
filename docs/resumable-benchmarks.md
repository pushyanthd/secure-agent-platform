# Run benchmarks in separate terminal sessions

Codex does not need to stay open. The CLI runs locally and persists its own state.
Run from the repository root, keep the run directory, and use the same checkout,
Python environment, model settings, and Docker tool image when resuming.
If `uv` is not on your shell's PATH, use `.venv/bin/uv` or invoke
`.venv/bin/agentguard` directly instead of `uv run --locked agentguard`.

## Start, pause, inspect, and resume

After the existing [model setup](local-model.md) and sandbox setup, start Docker
and the pinned model server in one terminal:

```sh
make model-serve
```

In another terminal, start the current 14-task development catalogue:

```sh
uv run --locked agentguard eval-suite --live \
  --suite scenarios/dev/suite-v3.json --max-episodes 10
```

This schedules **84 development episodes**, runs up to ten this session, then
prints `PAUSED`. Omit `--max-episodes` to keep running until you pause or the suite
finishes. Each progress line includes the run directory. Four-attack scheduling is
implemented in the newer development suites. The
[400-episode held-out release](release-evaluation.md) still needs its corpus, freeze,
and release-specific gate; this command does not create that benchmark.

**Press Ctrl+C once in the benchmark terminal to request a safe pause.** The
current episode finishes and its result is saved before the command exits. It
can take up to the remaining episode budget (normally 300 seconds), plus bounded
tool cleanup and reporting. SIGTERM requests the same drain. Child model HTTP and
Docker CLI processes use separate process groups so terminal Ctrl+C does not
prematurely terminate their work.

Once `PAUSED` appears, you can stop the model server, quit Docker, close the
terminal, or shut down the Mac. Restart Docker and the same model server before
continuing. A pause between episodes may last days; unstarted episodes receive
their ordinary budgets when they start.

Use the actual UUID directory printed by your command in place of `<run-id>`:

```sh
uv run --locked agentguard eval-status artifacts/suites/<run-id>
uv run --locked agentguard eval-resume artifacts/suites/<run-id> --max-episodes 10
```

Status needs no model or Docker. Resume infers the original suite, variants,
approval simulation, and live/replay mode. If you used custom setup files, pass
the same `--model-profile` and `--sandbox-manifest` options. Their resolved
contents/settings must match; a changed tool timeout or image is rejected.

For a quick no-model rehearsal:

```sh
uv run --locked agentguard eval-suite --suite scenarios/dev/tools-v2.json --max-episodes 2
# Substitute the directory printed above:
uv run --locked agentguard eval-resume artifacts/suites/<run-id>
```

These 24 episodes use authored replay and perform zero model trials. A paused
command exits zero with `PAUSED`; this does not mean the benchmark passed. On
completion, the existing smoke exit rules still apply: noncompleted episodes,
defended clean failures, or defended attack wins produce exit code 1. These are
not the future portfolio product gate.

## Abrupt interruption and honest accounting

A second Ctrl+C, at least half a second after the first, interrupts immediately.
The short interval absorbs duplicate signals forwarded by `uv run`.
A forced kill, terminal closure, or
machine shutdown before `PAUSED` may interrupt the active episode. On resume:

- Already journaled results are reused verbatim, including failures.
- A finished runtime result saved before the crash is graded without inference.
- A started episode without a finished result becomes `FAILED` with reason
  `BENCHMARK_INTERRUPTED`. It is never regenerated or silently retried.
- Committed effects, available execution traces, simulated reviews, saved final
  outputs, and raw model calls remain available to the independent grader.
- Missing or malformed model responses reserve the original output allowance;
  unknown generation is not reported as measured zero token consumption.
- Interrupted episode duration is `null`; timing summaries exclude it and expose
  the missing measurement. Incomplete attacked trials remain in the conservative
  worst-case attack bound, and any observed attacker win remains a win.

The rest of the original schedule continues. This intentionally favors complete,
honest trial accounting over restarting an unlucky episode. Use a single Ctrl+C
and wait for `PAUSED` for routine stopping. Never edit/delete failed rows to
improve results. Host-crash orphan-container reconciliation remains separate work;
the journal prevents duplicate benchmark execution, not all orphan computation.

## Persistence, compatibility, and evidence

The working `state.sqlite3` contains the complete schedule, started markers,
checksummed result records, and session history. An OS file lock permits one
benchmark process per run directory and releases automatically on process death.
This is a Mac/Linux local-disk contract, not a distributed worker lease. Unsafe
experimental profiles remain outside the authenticated application's defended
queue. Initialization must finish and print its first progress line before a
run is resumable.

`episodes.json` is a regenerable export of committed journal results. If a process
dies during JSON export, resume reconstructs it from SQLite. Keep the whole run
directory, including SQLite WAL files; never copy only the main database while
a process is running. Completed reports use SQLite's backup API.

Resume checks the pinned manifest against the journal, exact source snapshot,
Python/package versions, OS/architecture, fixture snapshots, model profile and
server metadata, model configuration, budgets, and tool backend. It uses saved
fixtures even if the original input files are moved. Source or environment changes
require returning to the original environment or starting a separately reported
run. These checks detect accidental mismatch, not malicious rewriting by the host
owner. Old published runs without a benchmark journal cannot be resumed.

`eval-status` reads the current journal. `progress.json` is exported at normal
session ends and includes session starts, finishes, and interrupted sessions;
an abrupt exit can leave that export stale until resume. A session with no known
end time is not proof that its process is still alive.

Only complete accounting produces the final report, raw-call export, database
backup, and checksum manifest. Then use `eval-analyze` and `eval-diagnostics`
normally. Partial results cannot become a successful analysis with a smaller
denominator. Repeating resume on an already finalized compatible run validates
the evidence and leaves it unchanged.

The regression tests exercise real child-process exits after committed effects
and before a model response, foreground-group SIGINT during a bounded child,
concurrent resume rejection, lost exports, completed-result recovery, and
compatibility failures. Model tests use doubles: they are not fresh inference
or a measured 400-episode evaluation.
