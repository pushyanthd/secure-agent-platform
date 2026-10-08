# Fresh-checkout storage CI fix

The [first hosted V1 run](https://github.com/pushyanthd/secure-agent-platform/actions/runs/37831928077)
passed contracts/portable outcomes/Docker, operator UI and installed packaging.
Its storage job stopped when the unprivileged measurement could not create
`artifacts/storage-measurement`: privileged volume creation had also created
the previously absent parent `artifacts` directory, owned by root.

The workflow now creates `artifacts` as the runner before privileged volume
administration. The same prerequisite is explicit in the storage runbook.
The runtime, graders, model, selected candidate and frozen outcomes are unchanged.

[Fresh-workspace reproduction](reproduction.json) first reproduces the original
permission error with a root-owned parent. A second fresh workspace uses the
fixed sequence: ordinary-user parent creation, privileged 64 MiB volume creation,
unprivileged exhaustion, privileged growth to 96 MiB, and unprivileged recovery.
All **18/18 checks pass** and both dedicated volumes are unmounted. This uses
authored responses, simulated lease expiry and zero fresh model calls.
Private logs, backing images and synthetic databases retain both attempts.
The [exact Windows-to-WSL rehearsal driver](reproduction-driver.txt) records
the normal and privileged operations separately; it never deletes the test data.

This is local Ubuntu/WSL verification of the actual failing setup sequence.
The corrected hosted run remains pending the user's push. Earlier evidence,
the failed hosted run, package attempts and checksum values are preserved.
