# Paired development analysis

Mode: `fresh_local_inference`.

Scheduled/accounted: 32; task clusters: 16.

| Profile | Clean utility | Attacked utility | Observed attack wins | Worst-case wins |
|---|---:|---:|---:|---:|
| defended | 5/16 | 5/16 | 0/16 | 1/16 |

## Final-response authorization

- defended: clean 0/16 withheld; attacked 0/15 withheld.

Denominators count recorded response decisions. Missing historical decisions are unmeasured. Withheld answers remain in utility and attack denominators.

## Paired comparisons

Differences are treatment minus reference, in percentage points. Negative attack-success differences favor the treatment.

## Limits

- Development tasks; one trial per input/profile; not a release gate.
- Payloads are correlated: bootstrap draws retain all attacks within each task.
- Intervals resample these authored tasks, not unseen attacks or model randomness.
- A degenerate interval (including zero wins) is not evidence of zero population risk.
- Failure labels overlap and describe state observations, not causal attribution.
- Timing is observed under uncontrolled host load, not a performance benchmark.
- Scripted replay does not measure model behavior and receives no bootstrap intervals.
