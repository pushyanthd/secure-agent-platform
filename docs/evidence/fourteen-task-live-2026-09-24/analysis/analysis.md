# Paired development analysis

Mode: `fresh_local_inference`.

Scheduled/accounted: 84; task clusters: 14.

| Profile | Clean utility | Attacked utility | Observed attack wins | Worst-case wins |
|---|---:|---:|---:|---:|
| baseline | 12/14 | 10/14 | 4/14 | 4/14 |
| prompt_only | 12/14 | 10/14 | 4/14 | 4/14 |
| defended | 14/14 | 13/14 | 0/14 | 0/14 |

## Paired comparisons

Differences are treatment minus reference, in percentage points. Negative attack-success differences favor the treatment.

### prompt_only versus baseline

- clean_utility: +0.0 pp; descriptive 95% interval [0.0, 0.0].
- attacked_utility: +0.0 pp; descriptive 95% interval [0.0, 0.0].
- observed_attack_success: +0.0 pp; descriptive 95% interval [0.0, 0.0].

Common clean-solved tasks: 12; excluded: 2.
Conditional observed attack wins, baseline: 2/12.
Conditional observed attack wins, prompt_only: 2/12.

### defended versus baseline

- clean_utility: +14.3 pp; descriptive 95% interval [0.0, 35.7].
- attacked_utility: +21.4 pp; descriptive 95% interval [0.0, 42.9].
- observed_attack_success: -28.6 pp; descriptive 95% interval [-50.0, -7.1].

Common clean-solved tasks: 12; excluded: 2.
Conditional observed attack wins, baseline: 2/12.
Conditional observed attack wins, defended: 0/12.

### defended versus prompt_only

- clean_utility: +14.3 pp; descriptive 95% interval [0.0, 35.7].
- attacked_utility: +21.4 pp; descriptive 95% interval [0.0, 42.9].
- observed_attack_success: -28.6 pp; descriptive 95% interval [-50.0, -7.1].

Common clean-solved tasks: 12; excluded: 2.
Conditional observed attack wins, prompt_only: 2/12.
Conditional observed attack wins, defended: 0/12.

## Limits

- Development tasks, one attack and one trial per task/profile; not a release gate.
- Intervals resample these authored tasks, not unseen attacks or model randomness.
- A degenerate interval (including zero wins) is not evidence of zero population risk.
- Failure labels overlap and describe state observations, not causal attribution.
- Timing is observed under uncontrolled host load, not a performance benchmark.
- Scripted replay does not measure model behavior and receives no bootstrap intervals.
