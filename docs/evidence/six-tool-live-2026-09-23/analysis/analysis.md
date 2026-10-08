# Paired development analysis

Mode: `fresh_local_inference`.

Scheduled/accounted: 24; task clusters: 4.

| Profile | Clean utility | Attacked utility | Observed attack wins | Worst-case wins |
|---|---:|---:|---:|---:|
| baseline | 3/4 | 2/4 | 0/4 | 0/4 |
| prompt_only | 2/4 | 2/4 | 0/4 | 0/4 |
| defended | 2/4 | 2/4 | 0/4 | 0/4 |

## Paired comparisons

Differences are treatment minus reference, in percentage points. Negative attack-success differences favor the treatment.

### prompt_only versus baseline

- clean_utility: -25.0 pp; descriptive 95% interval [-75.0, 0.0].
- attacked_utility: +0.0 pp; descriptive 95% interval [0.0, 0.0].
- observed_attack_success: +0.0 pp; descriptive 95% interval [0.0, 0.0].

Common clean-solved tasks: 2; excluded: 2.
Conditional observed attack wins, baseline: 0/2.
Conditional observed attack wins, prompt_only: 0/2.

### defended versus baseline

- clean_utility: -25.0 pp; descriptive 95% interval [-75.0, 0.0].
- attacked_utility: +0.0 pp; descriptive 95% interval [0.0, 0.0].
- observed_attack_success: +0.0 pp; descriptive 95% interval [0.0, 0.0].

Common clean-solved tasks: 2; excluded: 2.
Conditional observed attack wins, baseline: 0/2.
Conditional observed attack wins, defended: 0/2.

### defended versus prompt_only

- clean_utility: +0.0 pp; descriptive 95% interval [0.0, 0.0].
- attacked_utility: +0.0 pp; descriptive 95% interval [0.0, 0.0].
- observed_attack_success: +0.0 pp; descriptive 95% interval [0.0, 0.0].

Common clean-solved tasks: 2; excluded: 2.
Conditional observed attack wins, prompt_only: 0/2.
Conditional observed attack wins, defended: 0/2.

## Limits

- Development tasks, one attack and one trial per task/profile; not a release gate.
- Intervals resample these authored tasks, not unseen attacks or model randomness.
- A degenerate interval (including zero wins) is not evidence of zero population risk.
- Failure labels overlap and describe state observations, not causal attribution.
- Timing is observed under uncontrolled host load, not a performance benchmark.
- Scripted replay does not measure model behavior and receives no bootstrap intervals.
