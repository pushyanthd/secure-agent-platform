# Current trust boundary

This increment executes six fixed operations over synthetic state. The local
replay uses trusted Python; the isolated replay sends bounded JSON to a fixed
container entrypoint. The live loop uses the same isolated tools with a native
local model. No mode accepts model-authored code or shell commands.
The local authenticated control plane exposes defended task selection, redacted
inspection, cancellation, and approval review through the same-origin operator UI.
Completed suite reports also have a standalone, read-only browser viewer.

Trusted inputs are the fixture contract, resource metadata/ACLs, policy code,
selected experiment profile, operator review, and grader predicates. Document
bodies and action proposals are untrusted. Pydantic rejects unknown authority
fields and invalid tool arguments before execution. The live loop permits one
budgeted schema repair; a malformed proposal cannot dispatch a tool.

The defended profile enforces actor permissions and per-task scope. Reading a
confidential document, search snippet, or ticket preview marks the episode confidential. Subsequent internal writes
require review; shared writes are denied. Shared writes without confidential reads
also require review. Document shares always require review of source and destination;
updates bind the existing ticket and expected version. Baseline/prompt-only profiles deliberately disable these
business checks inside a synthetic episode. The latest
[live evidence](evidence/fourteen-task-live-2026-09-24/README.md) compares all three
profiles on fourteen development tasks; it cannot establish held-out or general attack protection.

SQLite `BEGIN IMMEDIATE` serializes preparation and effect application separately.
Computation runs between transactions, without holding the write lock. Resource
metadata is loaded from the episode, and approval hashes bind its full snapshot.
After computation, the host validates the returned effect and rechecks current
policy, cancellation, approval expiry/consumption, and the full state hash.
Live calls additionally pass an episode deadline, rechecked in the effect transaction.
Effect, approval consumption, idempotency output, and audit share one transaction.
Committed retries return their original result; changing an execution key's
arguments raises a conflict. Audit is append-only by convention, not tamper-proof.

Managed jobs additionally require a live lease token and claim generation in
every checkpoint and effect transaction, including the recheck after computation.
An expired worker cannot save a model response, finalize a run, or commit an effect.
Missing tokens cannot bypass fencing by calling the synchronous runtime. Cancellation
revokes the lease atomically. Approval decisions wake waiting jobs in the same
transaction; recovery revalidates the action's approval against current scope.
The model never receives lease tokens or reviewer nonces. Direct database access
remains trusted; this is not OS-level separation of the operator and worker.

`Store.review()` and `Store.approval()` are trusted operator library functions.
They must never become model tools. Their HTTP wrappers authenticate high-entropy
bearer tokens, derive reviewer identity from a trusted principal, and require owner,
actor, and workspace matches. Observer tokens cannot inspect review credentials or
mutate state. Approval hashes/nonces remain separate from authentication; neither
a nonce nor a worker lease establishes operator identity.

The API and worker have separate startup paths; only the API reads token fingerprints,
and credentials never enter worker settings or model/tool inputs. Both still run
under the same trusted OS user and access SQLite. This is HTTP authorization and
credential-flow separation, not protection against a compromised host-code worker.
API credentials are reloaded on server restart; there is no external identity provider.

Exact Host/Origin and Fetch Metadata checks, custom mutation headers, JSON-only
bounded bodies, and non-cacheable responses constrain browser requests. The service
has no cookies, permissive CORS, or trusted proxy headers. Status/timeline endpoints
omit raw responses, free text, approval nonces, and lease tokens. Exact canonical
action content is intentionally available to the owning reviewer. The UI renders
it as text under a restrictive CSP. Only the compiled shell/assets are public;
API authentication and host/origin checks remain active. Credentials live only in
tab memory; logout aborts requests and clears the view. The UI does not silently
replace inspected snapshots or retry reviews. See [the API contract](control-plane.md)
and [browser boundary and tests](operator-ui.md).

The development benchmark can opt into an exact-action reviewer
simulator. Its predeclared allowlist and task contract are trusted; it receives
no attack objectives or grader data. It cannot override a hard denial, and grants
still pass all gateway checks. The simulator is inside the trusted benchmark
process; it does not implement operator/worker credential separation. Ordinary
runtime use still pauses for review. See the [suite contract](development-suite.md).

The current grader detects exact synthetic canaries in final responses and ticket
title/body text and simulated share bodies. Grader v4 optionally checks canonical
base64 and lowercase hexadecimal encodings of UTF-8 canaries when declared by the
fixture. It does not detect arbitrary encodings or paraphrases; existing fixtures
remain plaintext-only.
The expanded tool suite also grades search/list results, ticket versions, protected
ticket contents, and exact shared documents. See [the tool contract](tool-surface.md).
The original ten-task suite
also checks stored read outcomes and attempts, ticket counts, and final-answer
requirements. Its ten self-authored development payloads exercise several
authorization rules but cannot establish broad attack coverage or held-out ASR.

The [twenty-task development corpus](development-corpus.md) includes authored
counterexamples to two boundaries: legacy contracts authorize updates by project,
and final response text does not pass through the tool gateway. Four protected-sibling
mutations and three response disclosures succeed in the original expansion replay.
The [gateway-v3 treatment](adr-003-ticket-scope-and-response-boundary.md) adds explicit
ticket update lists to the new default catalogue and blocks those four mutations.
Missing/null lists retain project-wide update authority for legacy contracts;
empty lists deny every update. The three response disclosures remain failures.
These are reachable scripted behaviors, not measured model attack-success rates. Review
of sensitive tool effects does not prevent a model from disclosing source text
in its final answer.

An opt-in [response clearance contract](adr-004-response-clearance-treatment.md)
now withholds final text from an internal-only destination after any confidential
read/search/list exposure. It uses current scope and taint at final commit, retains
lease/cancellation checks, and does not use hidden grader information. Missing/null
scope preserves legacy behavior. This coarse treatment blocks harmless output too;
the known clean-triage utility failure remains visible. The default catalogue has
not adopted it. Raw replies and source-bearing evaluation artifacts remain trusted
local evidence, outside the final-response confidentiality claim.

The container backend uses no host mounts or network, a read-only root filesystem,
unprivileged UID, dropped capabilities, no-new-privileges, default seccomp, and
bounded resources. A separate diagnostic image probes these restrictions. Tool
stdout/stderr and stdin writes are bounded by size and wall time. The supervisor
explicitly removes a timed-out container; killing the Docker CLI alone is not
sufficient. Failure to confirm cleanup raises a typed error. If the supervisor
itself crashes, orphan reconciliation is still pending; this is distinct from
the tested tool-process timeout path.

Model requests use literal loopback addresses, no proxy or redirect following,
and bounded subprocess HTTP. Raw model responses commit before parsing/dispatch.
Token counting uses the server template; oversized contexts are rejected without
truncating the task. Step, generated-token, result-size, and wall-time limits apply.
Local model/runtime hashes and reported server identity are checked; a malicious
local model server or host can still lie about its identity or metering.

No microVM-grade isolation or resistance to kernel/container-engine exploits is
claimed. A malicious operator, compromised host, and modified trusted images are
outside this lab's boundary. Docker's configured engine/context is trusted.

The offline analyzer verifies checksums and schedule/result identity before
exporting comparisons. Checksum verification detects inconsistent evidence; it
does not authenticate evidence against a malicious host owner. The standalone
viewer escapes embedded JSON delimiters and writes document/model content only
through DOM text APIs. Its content security policy limits executable code and
styles to the bundled hashes and denies network connections. It exposes no tool
execution, approval, authentication, or service endpoint. Its rendering tests are
separate from the control-plane authentication/CSRF and operator UI tests.

Not implemented: immediate in-flight cancellation, model-failure retries,
hardened worker isolation, or hosted multi-tenancy.
The control plane is limited to trusted loopback use. The local inference
server has no business credentials; its built-in agent tools and browser UI are disabled.

## Opt-in reviewed-effect receipts

[ADR 005](adr-005-verified-effect-receipts.md) permits a trusted task author to
release one completion bit for an exact reviewed ticket update. The finalizer
checks the committed execution, consumed approval, current contract/project, and
resulting ticket state inside its fenced transaction. Its only response text is
“Ticket update confirmed.”; model prose and resource text are not interpolated.
An absent or stale proof withholds the output. Cancellation and deadlines still
suppress delivery. This does not establish that every task requirement was met;
the independent state grader remains authoritative. The completion bit and timing
can reveal information, so receipt authority is explicit and opt-in. Raw local
evidence and baseline disclosures remain outside the delivery boundary.

[ADR 006](adr-006-model-visible-receipt-scope.md) adds an opt-in template-only
presentation of that receipt. The exact action remains in trusted storage and
all verification checks still apply. Saved model scope is presentation data,
never reconstructed authorization. Recovery preserves it while tool and final
response commits consult current authority. Omitting the action from the prompt
does not enforce task ordering or prove that the model encounters an attack;
independent workflow grades and recorded-request exposure measure those outcomes.
