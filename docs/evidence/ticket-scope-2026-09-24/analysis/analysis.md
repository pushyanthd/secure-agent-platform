# Paired development analysis

Mode: `scripted_suite_replay`.

Scheduled/accounted: 90; task clusters: 6.

| Profile | Clean utility | Attacked utility | Observed attack wins | Worst-case wins |
|---|---:|---:|---:|---:|
| baseline | 6/6 | 0/24 | 24/24 | 24/24 |
| prompt_only | 6/6 | 0/24 | 24/24 | 24/24 |
| defended | 6/6 | 21/24 | 3/24 | 3/24 |

## Paired comparisons

Differences are treatment minus reference, in percentage points. Negative attack-success differences favor the treatment.

### prompt_only versus baseline

- clean_utility: +0.0 pp; scripted replay, no interval.
- attacked_utility: +0.0 pp; scripted replay, no interval.
- observed_attack_success: +0.0 pp; scripted replay, no interval.

Common clean-solved tasks: 6; excluded: 0.
Conditional observed attack wins, baseline: 24/24.
Conditional observed attack wins, prompt_only: 24/24.

### defended versus baseline

- clean_utility: +0.0 pp; scripted replay, no interval.
- attacked_utility: +87.5 pp; scripted replay, no interval.
- observed_attack_success: -87.5 pp; scripted replay, no interval.

Common clean-solved tasks: 6; excluded: 0.
Conditional observed attack wins, baseline: 24/24.
Conditional observed attack wins, defended: 3/24.

### defended versus prompt_only

- clean_utility: +0.0 pp; scripted replay, no interval.
- attacked_utility: +87.5 pp; scripted replay, no interval.
- observed_attack_success: -87.5 pp; scripted replay, no interval.

Common clean-solved tasks: 6; excluded: 0.
Conditional observed attack wins, prompt_only: 24/24.
Conditional observed attack wins, defended: 3/24.

## Limits

- Development tasks, one trial per clean/attack input and profile; not a release gate.
- Payloads are correlated: bootstrap draws retain all attacks within each task.
- Intervals resample these authored tasks, not unseen attacks or model randomness.
- A degenerate interval (including zero wins) is not evidence of zero population risk.
- Failure labels overlap and describe state observations, not causal attribution.
- Timing is observed under uncontrolled host load, not a performance benchmark.
- Scripted replay does not measure model behavior and receives no bootstrap intervals.
