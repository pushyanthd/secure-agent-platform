# Offline paired analysis

`agentguard eval-analyze` analyzes one completed development-suite run.
It works with existing replay or live bundles, without starting Docker or the model:

```sh
uv run --locked agentguard eval-analyze artifacts/suites/<run-id> \
  --output artifacts/analyses/<run-id>
```

The output directory must be new and outside the input evidence directory. The
command exports `analysis.md`, `analysis.json`, `explorer.html`, the exact analyzer
and viewer source, and checksums. Input checksums and experiment provenance accompany the analysis.
The original evidence is never rewritten. Default bootstrap settings are 5,000
resamples with seed 42; `--resamples` and `--seed` record explicit alternatives.

Open `explorer.html` in a browser for a standalone comparison of any task's clean
or attacked episodes under two profiles, with a selector for each attack variant.
It shows original task text, tool
proposals, decisions, simulated reviews, final model claims, and independent
state grades. All assets are embedded; the viewer makes no network requests.
Untrusted text is assigned through DOM `textContent`; embedded JSON escapes HTML
delimiters. A content security policy permits only the exact bundled script and
style. This static artifact has no execution or approval controls and does not
replace the planned authenticated application UI.

## Evidence contract

The analyzer checks every file listed in the input checksum manifest, rejects
paths escaping the evidence directory, and requires checksummed reports, manifests,
incremental episode records, source snapshots, and model-call records. Report
and manifest/episode snapshots must agree; fixture and source hashes must match
the manifest. These checks detect accidental alteration and inconsistent bundles.
They do not authenticate an operator who can replace files and their hashes.

Each scheduled episode must have exactly one result with the same episode ID,
task, profile, input type, and attack ID. Run-manifest schema 2 requires one clean
episode and every declared attack per task/profile. Its attack catalogue must
match the pinned fixture snapshots. Legacy schema 1 runs remain readable as one
primary attack per task/profile. Missing results, duplicates, altered
identities, invalid grades, or success attributed to an unfinished episode make
the analysis unusable. The CLI exits nonzero and writes no analysis. Use
`eval-resume` to account for interruptions and finish the original schedule before
analysis; this command does not invent missing grades or resume inference.
Interrupted duration is null and excluded from timing summaries, with the unknown
count retained. See [multiple-attack contracts and the pilot](multi-attack-evaluation.md).
Repeated seeds still need a separate observation schema.

All counts are recalculated from episode observations, independently of the
report's summary counts. Failed, cancelled, budget-exhausted, and approval-waiting
episodes remain in the denominator. An observed attacker win remains a win even
if the episode later fails. Each unfinished attacked episode without an observed
win also counts toward the conservative worst-case bound, exactly once.

## Comparisons

Every pair of profiles receives:

- Clean utility, attacked utility, and observed attack-success differences,
  expressed as treatment minus reference.
- Conditional observed attack success on the common set of tasks that both
  profiles solved cleanly, including all their attack variants. Included and
  excluded task IDs are exported; the rate denominator counts attack episodes. With no
  common clean successes, the rate is undefined (`null`), never zero.
- Descriptive 95% paired percentile bootstrap intervals for fresh inference.
  Each draw resamples task IDs with replacement, keeping the clean result, every
  attack variant, and every profile together. Shared draws preserve pairing across
  treatments. Ratios use summed numerators and denominators within each draw;
  tasks with more payloads retain their episode weight.

Absolute rates include raw numerators and denominators. Reports also retain
status counts, unresolved attacks, simulated review counts, generated tokens,
model calls, observed episode timing, and per-episode failure labels. Labels such
as missing required ticket content, unauthorized effects, and task failure with a
denial can overlap. They describe observations and do not establish causes or
automatically classify a final response as a false completion claim.

Analyzer v4 also records clean/attacked response-authorizations and denials, and
labels task failures with withheld responses as `response_withheld`. A completed
episode with an intentionally withheld response is a resolved policy outcome;
its missing response can still fail the unchanged utility predicate. All episodes
remain in utility/attack denominators. Historical runs without response decisions
are unmeasured at this boundary, with zero recorded decisions rather than an
inferred protection rate. The viewer displays the decision separately from the
final text. See [the opt-in treatment and utility cost](adr-004-response-clearance-treatment.md).

## Interpretation limits

Self-authored development tasks and a small set of fixed payloads are too
limited for a release-security claim. Task bootstrap intervals describe variation
in these fixtures. They do not estimate uncertainty over new attack families or
repeat sampling from the model. A degenerate interval, including `[0, 0]` for no
observed attack wins, does not establish zero population risk. Grader v4 detects
explicitly declared canonical base64/hex canaries in addition to plaintext;
undeclared encodings, other transformations, and paraphrases remain outside these
predicates. Older fixtures retain plaintext-only semantics. See [the corpus and
grader contract](development-corpus.md).

Replay receives counts and paired differences for checking contracts, but no
bootstrap intervals or model-behavior claims. Runtime observations include host
load and container overhead; the analyzer does not isolate policy latency,
inference latency, human review time, or whole-machine memory. No release gate is
implemented by this command. Its successful exit means the analysis is usable,
not that the model meets the architecture's utility or security objectives.

## Runtime diagnostics

The separate diagnostics command reconciles the same checksum-verified evidence
with its saved model-call ledger:

```sh
uv run --locked agentguard eval-diagnostics artifacts/suites/<run-id> \
  --output artifacts/diagnostics/<run-id>
```

It rejects foreign or duplicate call IDs, missing calls, inconsistent step
sequences, and token totals that disagree with the episode report. Lost or malformed
responses keep their reserved allowance separate from measured generated tokens.
The exported JSON/Markdown reports include reported prompt/output tokens, context
headroom, observed call/episode durations, recorded decisions for each tool, and
independently graded task outcomes for episodes containing a denial.

These are descriptive diagnostics. Server-reported usage is not independent
metering, context headroom is not the tokenizer's separately measured admission
count, and call duration includes prompt processing as well as generation. Tool
coverage counts recorded policy decisions; a failed computation can leave no
completed trace entry. Task success after denial is not a causal recovery estimate;
an expected refusal can succeed without another allowed action. Empty recovery
denominators and missing timing measurements remain explicit.

Diagnostics are written outside the original run, with source and checksums.
They never change a grade, retry a model call, or convert replay into fresh evidence.
