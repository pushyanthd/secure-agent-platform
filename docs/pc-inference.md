# Windows 11 / RTX 5080 inference

## PC-only application and evaluation

Verified October 7, 2026: 679 Python tests, lint/format/strict typing, 16 browser
tests, 24 Docker containment probes, authored recovery/HTTP smoke checks, and the
24-episode isolated tool replay passed. A real structured-generation probe and
two fresh defended launch-task episodes also passed (clean and attacked). The
ten-task development schedule subsequently completed all 20 trials: 10/10 clean
successes, 9/10 attacked successes, zero observed attacker wins, and no unfinished
trials. The [retained evidence](evidence/pc-development-2026-10-07/README.md)
includes its omitted-read failure and supports offline state regrading.
The [new 32-trial utility study](evidence/pc-utility-2026-10-07/README.md) also
completed: checklist clean 6/8 and attacked 5/8 missed its frozen 7/8 and 6/8
selection thresholds. Neither study revises the historical release gate.

The [PC capacity guard pilot](evidence/pc-completion-guard-2026-10-07/README.md)
then qualified at 4/4 exact successes versus 3/4 control. Its
[broader 32-trial follow-up](evidence/pc-completion-broad-2026-10-07/README.md)
committed every required effect but still rejected the candidate at 6/8 clean
and 6/8 attacked successes. The next gap is decision correctness, including
corrections described without a committed update. All 40 new outcomes support
offline regrading; 711 Python tests and lint/format/strict typing passed in a
separate same-PC checkout. The earlier browser and containment checks are unchanged.

The application, SQLite state, operator console, worker, Docker tools, evaluations,
and GPU inference can run together on this PC. The supported PC arrangement uses
Ubuntu under WSL2 for the application and the pinned Windows CUDA server for
inference. A Mac and SSH tunnel are unnecessary for this arrangement.

Install Ubuntu as a WSL2 distribution and enable its Docker Desktop integration.
The Ubuntu working copy lives at `~/secure-agent-platform`, with its own Linux
Python environment, Node runtime, credentials, databases, and evidence. Model
weights and Windows CUDA files remain in the original Windows checkout. Keeping
the application in the Linux filesystem preserves POSIX credential permissions
and avoids executing the application from a OneDrive mount.

The setup helper `scripts/pc/setup_wsl.py`, run with Ubuntu's `python3` from the
Windows checkout's `/mnt/c/...` path, creates that working copy and preserves
current source edits. It requires `make`, `curl`, `python3-venv`, and `xz-utils`
in Ubuntu. It installs uv 0.12.18, the locked Python dependencies, checksum-checked
Node 24.21.0 for Linux x64, and locked frontend dependencies. It refuses to
overwrite an existing working copy. Source text uses LF endings; frozen evidence
keeps its original Git bytes and checksums.

Enable `networkingMode=mirrored` in the Windows user's `.wslconfig` and restart
WSL. The reviewed `scripts/pc/enable-wsl-loopback.ps1` helper preserves other
settings and backs up an existing file. This permits Ubuntu to reach the Windows
server at `127.0.0.1:8101`. No model HTTP port needs a LAN binding. See
[Microsoft's mirrored networking documentation](https://learn.microsoft.com/en-us/windows/wsl/networking#mirrored-mode-networking).

In a PowerShell terminal at the original Windows checkout, start inference:

```powershell
.\.venv\Scripts\python.exe scripts\pc\model_server.py serve
```

In Ubuntu at `~/secure-agent-platform`, configure the Windows artifact location
once, using the actual mounted checkout path:

```sh
cd ~/secure-agent-platform
.venv/bin/python scripts/pc/configure_wsl.py --windows-root /mnt/c/path/to/secure-agent-platform
.venv/bin/python scripts/pc/probe_wsl.py
make check ui-build ui-check
make sandbox-build sandbox-smoke
```

The ignored `artifacts/pc-wsl/model-profile.json` records the machine-local paths
and committed Windows runtime pins. Preflight checks the GGUF size and SHA-256,
each pinned ZIP, every installed runtime file, and the server's Windows model
path, alias, build, context, template, and slot count. The probe then performs one
real structured generation. Its evidence is a feasibility check, not a release
score. Mac preflight and historical frozen evidence retain their original path.

Initialize the live application once, then start API and worker in separate
Ubuntu terminals:

```sh
.venv/bin/uv run --locked agentguard control-init --model-profile artifacts/pc-wsl/model-profile.json
make api-serve       # Ubuntu terminal 1
make worker          # Ubuntu terminal 2
```

Open `http://127.0.0.1:8000/` in the Windows browser. Read
`artifacts/control/operator.token` locally for access; do not paste credentials
into chat. Setup refuses to overwrite an existing control directory.

Alternatively, `.venv/bin/python scripts/pc/start_app.py` initializes the same
live profile if needed and starts API and worker as background processes. It
records their PIDs in `artifacts/control/processes.json` and writes separate
local logs. It refuses to start over a listener on port 8000. These processes
and the Windows model server must be restarted after a PC/WSL shutdown.

Start a bounded fresh development comparison with the PC profile explicitly:

```sh
.venv/bin/uv run --locked agentguard eval-suite --live --variants defended \
  --model-profile artifacts/pc-wsl/model-profile.json --max-episodes 2
```

Preserve the resulting run and resume with the same profile and source. This is
development evidence; improved GPU throughput does not establish improved utility.
After source edits in the Windows checkout, `scripts/pc/check_wsl.sh` explicitly
copies those changes to the Ubuntu working copy and runs validation. It preserves
ignored local environments, databases, credentials, and evidence.

## Historical Windows inference setup

On September 29, 2026, the pinned Qwen3.5-9B Q4_K_M model and llama.cpp b11149
Windows CUDA 13.4 runtime were downloaded to this PC and verified against the
committed sizes and SHA-256 checksums. The server loaded on the RTX 5080 and
served a structured generation through the application's own model transport.
The model endpoint is `http://127.0.0.1:8101`. Remote evaluation from the Mac
has not yet been tested.

The Mac retains the app, Docker tools, database, and evidence. The intended PC
role is model inference only, listening on `127.0.0.1:8101` and reached from the
Mac through an SSH tunnel on a separate local port, `127.0.0.1:8102`.

## Run on the PC

From the repository root in PowerShell:

```powershell
.\.venv\Scripts\python.exe scripts\pc\model_server.py setup   # First time; ~6.3 GB
.\.venv\Scripts\python.exe scripts\pc\model_server.py serve   # Keep this window open
```

In another PowerShell window:

```powershell
.\.venv\Scripts\python.exe scripts\pc\model_server.py probe
```

`setup` resumes interrupted downloads, checks their pinned sizes and SHA-256
digests, and installs the verified ZIP contents under ignored `artifacts/`.
`serve` checks those files again, binds only to loopback, and loads 99 GPU layers.
The probe checks the model alias, server build, GGUF path, context, tokenization,
and a small structured completion through `agentguard.model.LocalModel`. Stop a
foreground server with Ctrl+C. The server does not start automatically after a
reboot. On this PC the measured initial load used about 6.8 GB of GPU memory;
the six-token probe completed in about 0.35 seconds after load.

## Optional Mac connection still to do

- [OpenSSH bootstrap](../scripts/pc/bootstrap-ssh.ps1), based on Microsoft's
  [installation](https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh_install_firstuse)
  and [administrator key-management](https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh_keymanagement)
  instructions. It requires an elevated PowerShell window as the intended PC
  administrator and a trusted Private LAN. It preserves existing keys, adds the
  supplied public key, and restricts the standard SSH firewall rule to the
  private local subnet. It does not open the model HTTP port.
- [Runtime asset pins](../config/pc-windows-runtime.json) for the official
  [llama.cpp b11149 Windows CUDA 13.4 release](https://github.com/ggml-org/llama.cpp/releases/tag/b11149).
  The executable and CUDA dependency archives total approximately 573 MB.
  The archives and GPU execution have now been verified on this PC with driver
  610.47. This is a runtime observation, not a general driver compatibility claim.
- A dedicated SSH key in the ignored `artifacts/pc-inference/` directory on the
  original Mac. The private key stays on the Mac and is excluded from Git.
  `bootstrap-ready.ps1` in that directory contains the public key and is ready
  to paste into an elevated PowerShell window on the PC.

The PowerShell bootstrap has been reviewed against the documentation but has
not been executed or syntax-checked by PowerShell on this Mac.

## Connect the Mac application

1. On the PC, paste/run `artifacts/pc-inference/bootstrap-ready.ps1` from the Mac
   in **PowerShell as Administrator**. If it reports a Public network, mark the
   trusted home LAN Private in Windows Network settings, then rerun.
2. Record its SSH username, LAN IPv4 address, Ed25519 host-key fingerprint, and
   `nvidia-smi` GPU/driver/memory output. No password or private key is needed
   in chat. Compare the PC's host-key fingerprint when first connecting.
3. Connect with the dedicated key and verify the host-key fingerprint. The model
   and runtime are already installed on this PC; run the probe again after the
   SSH tunnel is established.
4. Implement and test the remote inference preflight before running an eval.
   The current local preflight intentionally requires local model/runtime files
   and an exact local server path; an SSH tunnel alone does not satisfy it.
   Do not remove those checks or label a remote server as locally verified.
5. Freeze a fresh development comparison with the remote model and runtime
   evidence. Preserve the Mac studies and their source fingerprints. Validate
   decision correctness and useful effects before a new 400-trial release study.

The bootstrap grants key access under Windows' administrator-account OpenSSH
convention. Stop the `sshd` service and remove this project's public-key line
from `C:\ProgramData\ssh\administrators_authorized_keys` when that access is no
longer wanted. Leave unrelated authorized keys intact.
