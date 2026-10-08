# Paired development analysis

Mode: `fresh_local_inference`.

Scheduled/accounted: 60; task clusters: 10.

| Profile | Clean utility | Attacked utility | Observed attack wins | Worst-case wins |
|---|---:|---:|---:|---:|
| baseline | 8/10 | 6/10 | 4/10 | 4/10 |
| prompt_only | 9/10 | 6/10 | 4/10 | 4/10 |
| defended | 10/10 | 8/10 | 0/10 | 0/10 |

## Paired comparisons

Differences are treatment minus reference, in percentage points. Negative attack-success differences favor the treatment.

### prompt_only versus baseline

- clean_utility: +10.0 pp; descriptive 95% interval [0.0, 30.0].
- attacked_utility: +0.0 pp; descriptive 95% interval [0.0, 0.0].
- observed_attack_success: +0.0 pp; descriptive 95% interval [0.0, 0.0].

Common clean-solved tasks: 8; excluded: 2.
Conditional observed attack wins, baseline: 2/8.
Conditional observed attack wins, prompt_only: 2/8.

### defended versus baseline

- clean_utility: +20.0 pp; descriptive 95% interval [0.0, 50.0].
- attacked_utility: +20.0 pp; descriptive 95% interval [0.0, 50.0].
- observed_attack_success: -40.0 pp; descriptive 95% interval [-70.0, -10.0].

Common clean-solved tasks: 8; excluded: 2.
Conditional observed attack wins, baseline: 2/8.
Conditional observed attack wins, defended: 0/8.

### defended versus prompt_only

- clean_utility: +10.0 pp; descriptive 95% interval [0.0, 30.0].
- attacked_utility: +20.0 pp; descriptive 95% interval [0.0, 50.0].
- observed_attack_success: -40.0 pp; descriptive 95% interval [-70.0, -10.0].

Common clean-solved tasks: 9; excluded: 1.
Conditional observed attack wins, prompt_only: 3/9.
Conditional observed attack wins, defended: 0/9.

## Limits

- Development tasks, one attack and one trial per task/profile; not a release gate.
- Intervals resample these authored tasks, not unseen attacks or model randomness.
- A degenerate interval (including zero wins) is not evidence of zero population risk.
- Failure labels overlap and describe state observations, not causal attribution.
- Timing is observed under uncontrolled host load, not a performance benchmark.
- Scripted replay does not measure model behavior and receives no bootstrap intervals.
