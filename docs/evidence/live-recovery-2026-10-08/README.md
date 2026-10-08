# Live recovery and cancellation on the PC profile

October 8, 2026. Four controlled boundaries on the exposed `launch-scope`
workflow used the pinned native Windows CUDA model, real WSL workers and the
unchanged immutable Docker tool image. Eleven fresh native generation calls
were recorded. Default configuration was not promoted.

| Boundary | Observation |
|---|---|
| Saved response before tool computation | Actual SIGKILL; real lease expiry; saved response reused; independently successful completion; exactly one ticket |
| Committed ticket before runtime checkpoint | Actual SIGKILL; recovery retained the effect and did not duplicate it; independently successful completion |
| Real paused runner with withheld stdin | Actual SIGKILL left the runner orphaned; restart identified its dead Linux owner and removed it; Docker CLI exited 137; recovery independently succeeded |
| Native second completion before response persistence | Controller cancelled the job after the read; stale response was not saved, no ticket committed and no response was regenerated |

The original report retained **36/37 checks** and reports failure. Its single
failed assertion searched Docker's absence message for uppercase `No such`;
Docker 29.8.2 emitted lowercase `no such object`. The separately retained
[observer correction](measurement/observer-correction.json) confirms the same
container's removal and CLI exit, with **6/6 checks and zero new model calls**.
The failed report and original grades were not rewritten. The published runner
is the exact measured version; the current repository observer accepts the
lowercase message for future measurements.

[Declaration](measurement/declaration.json), [original report](measurement/report.json),
all native responses, journal snapshots, outcomes, observer correction and
source archive are retained. Publication canonicalizes JSON and omits expired
lease token fields; original files and databases remain privately retained.
Independent grading opened only temporary database copies. The exact source
passed **818 tests**, lint, formatting and strict types. The separate Docker
29.8.2 probe report passes **24/24** containment checks.

This is four faults on one synthetic workflow and one sampling seed. Container
pausing/input withholding is a deliberate trusted fault hook. Cancellation
occurs after native completion; it does not demonstrate physical interruption of
GPU inference. Cleanup occurs when a controller restarts; no immediate cleanup
while every controller is dead is claimed. Unlabelled, foreign-host, other-image
and live-owner containers are preserved. Linux ownership labels are not an
authorization boundary against a trusted host administrator with Docker access.

Network observations are published separately. The original 400-trial gate
remains FAIL; the original forty templates and this workflow are exposed.
