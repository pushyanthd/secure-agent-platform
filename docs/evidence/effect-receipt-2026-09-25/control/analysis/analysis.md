# Paired development analysis

Mode: `scripted_suite_replay`.

Scheduled/accounted: 90; task clusters: 6.

| Profile | Clean utility | Attacked utility | Observed attack wins | Worst-case wins |
|---|---:|---:|---:|---:|
| baseline | 6/6 | 0/24 | 24/24 | 24/24 |
| prompt_only | 6/6 | 0/24 | 24/24 | 24/24 |
| defended | 5/6 | 20/24 | 0/24 | 0/24 |

## Final-response authorization

- baseline: clean 0/6 withheld; attacked 0/24 withheld.
- prompt_only: clean 0/6 withheld; attacked 0/24 withheld.
- defended: clean 1/6 withheld; attacked 4/24 withheld.

Denominators count recorded response decisions. Missing historical decisions are unmeasured. Withheld answers remain in utility and attack denominators.

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

- clean_utility: -16.7 pp; scripted replay, no interval.
- attacked_utility: +83.3 pp; scripted replay, no interval.
- observed_attack_success: -100.0 pp; scripted replay, no interval.

Common clean-solved tasks: 5; excluded: 1.
Conditional observed attack wins, baseline: 20/20.
Conditional observed attack wins, defended: 0/20.

### defended versus prompt_only

- clean_utility: -16.7 pp; scripted replay, no interval.
- attacked_utility: +83.3 pp; scripted replay, no interval.
- observed_attack_success: -100.0 pp; scripted replay, no interval.

Common clean-solved tasks: 5; excluded: 1.
Conditional observed attack wins, prompt_only: 20/20.
Conditional observed attack wins, defended: 0/20.

## Limits

- Development tasks, one trial per clean/attack input and profile; not a release gate.
- Payloads are correlated: bootstrap draws retain all attacks within each task.
- Intervals resample these authored tasks, not unseen attacks or model randomness.
- A degenerate interval (including zero wins) is not evidence of zero population risk.
- Failure labels overlap and describe state observations, not causal attribution.
- Timing is observed under uncontrolled host load, not a performance benchmark.
- Scripted replay does not measure model behavior and receives no bootstrap intervals.
