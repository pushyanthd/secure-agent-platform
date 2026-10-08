# V1 console walkthrough

This unedited browser capture demonstrates the real authenticated console, API,
durable queue, authorization gateway, exact-action review and transactional
effects. Model responses are authored fixtures: the video makes zero fresh
model calls. Explanatory cards identify the separate 58-trial candidate
regression and its exposed, single-seed scope.

[2:46 recording](walkthrough.webm), capture metadata, the exact script and reviewed
frames accompany this publication. Private control state, tokens, request
headers and server logs are excluded. The original
[October 7 recording](../portfolio-walkthrough-2026-10-07/README.md) remains intact.

The capture checks acknowledgement before approval, disabled review during API
restart, one committed ticket after approval, forbidden-read denial and queued
cancellation without an effect. API restart is not a worker-crash test; idle
worker invocation is not replay; queued cancellation is not in-flight model
cancellation. Live fault and containment measurements are linked separately.

Chromium decoded 166.16 seconds at 1440 × 1100. Eight frames at 5, 40, 61, 75,
94, 114, 133 and 159 seconds were visually inspected for legibility, fixture
labels and absence of displayed credentials. They show the console, disabled
exact-action review, completion, denied read, cancellation and result/closing
cards. Controller observation times are not exact encoded seek positions;
capture.json records 171.354 seconds of controller elapsed time. No cuts, speed
adjustments or audio were added.
