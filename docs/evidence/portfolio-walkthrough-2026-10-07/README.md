# Recorded portfolio walkthrough

[Play or download the 3:06 recording](walkthrough.webm) |
[Local HTML player](player.html) | [Capture provenance](capture.json)

This unedited 1440 x 1100 browser capture uses the real authenticated console,
API, durable queue, gateway, exact-action review and SQLite effects. Model
responses are authored fixtures. It makes **zero fresh-model evaluation trials**;
the visible mode badge and opening card say so. The clip has explanatory cards
and no audio. The original 400-trial release gate remains FAIL.

The capture asserts that review pauses and requires acknowledgment, an API
restart disables review until reconnected, approval commits one ticket, an idle
worker call leaves its count at one, a forbidden read is denied, and cancellation
before execution leaves no ticket. It records zero browser page errors.
API restart is not a worker-crash test; an idle worker call is not replay of a
committed generation; queued cancellation is not in-flight cancellation.

[Playback metadata](playback-review.json) records successful Chromium decoding,
a 186.16-second duration and full-resolution frames at eight timestamps. Those
frames were visually inspected for legibility, correct mode/result labels and
absence of displayed credentials. They cover the opening, exact action, disabled
review, completion, denied read, cancellation and result/closing cards. Only
allowlisted video, screenshots, provenance and the capture script are published;
private control state, tokens, headers, traces and server logs remain local.

The controller elapsed time in capture.json is 171.76 seconds. Encoded playback
is longer; observation timestamps describe controller time rather than exact
video seek positions. No cuts, speed adjustments or voice narration were added.

To reproduce, build the frontend and install Playwright Chromium in the configured
Linux/WSL checkout, then choose a fresh output directory:

```sh
make ui-build
cd frontend && npx --no-install playwright install chromium && cd ..
make ui-record RECORDING_OUTPUT=artifacts/my-walkthrough
```

[Exact capture script](capture-script.mjs) uses the existing out-of-band fixture
driver and an ephemeral API port. It adds no test routes or overlays to the
application. Chapter cards are separate pages. The script retains failed captures
and refuses existing output directories. Source and input hashes bind the
historical figures to their original publications. Local checksums establish
consistency, not independent attestation. [Reviewer path](../../reviewer-walkthrough.md).
