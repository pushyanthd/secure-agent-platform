# Measured offline project execution

October 8, 2026, **18:06:39–18:25:08 UTC**. Elevated Windows TCPIP ETW
observation covered the native CUDA model during all four live fault cases and
the newly declared 58-trial candidate regression. Linux `strace -ff` covered each
controller/worker and its descendants, including HTTP transports and Docker CLI.

- Windows decoded **990,563 events, zero events lost**. Exactly **3,905** events
  carry the model's explicit owning PID; they describe **781** loopback endpoint
  lifecycles and **zero observed public remote endpoints**. Every parsed address
  in those model-owned events is `127.0.0.1`.
- Linux retained **352 + 4,256 thread/process trace files**, all with terminal
  records. The only observed Internet socket peer was `127.0.0.1`; no unknown
  peer address remained. Traced connect attempts numbered **41 + 739**. One
  additional preparation `/props` request accounts for the 781st Windows accept.
- The run made **257 fresh generation calls**: eleven live-fault calls and
  246 candidate calls. Tokenization, template and provenance requests also used
  local inference. No public or paid API request was observed for those processes.
- Container execution used the immutable tool image with `network=none`;
  [24/24 Docker 29.8.2 containment probes](../live-recovery-2026-10-08/docker-29.8.2-probes.json)
  passed separately. Docker daemon/container processes are outside the Linux
  controller descendant trace, so the container boundary has this separate proof.

[Windows assessment](network-assessment.json), [model-owned events](model-events.json),
[Linux observations](linux-observation.json), provider schemas, trace-loss summary
and original-input hashes are retained. Raw Windows ETL/CSV and unrelated host
traffic remain private; publication does not imply the desktop had no other traffic.

Two failed extraction attempts remain recorded in [publication.json](publication.json),
with exact observer sources and hashes of their privately retained original
reports. The first confused event-header execution context with connection
ownership. The second reused a last-known connection pointer owner after an
allocation was recycled. The flagged external connection had a different explicit
owning PID. Final attribution uses **explicit owning PID payloads only**. These
corrections made zero new inference calls and did not change a behavioral grade.

This finite observation covers process-owned endpoint lifecycle events, not
every packet, every host service, a firewall guarantee or permanent enforcement.
Linux syscall tracing, the native endpoint observation and pinned container
network denial provide their stated scopes together. It does not establish
production readiness, independent reproduction or universal offline behavior.
