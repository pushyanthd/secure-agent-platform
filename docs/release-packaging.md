# V1 packaging and publication

The local V1 package and validation are prepared. The user performs all GitHub
activity using the [exact PowerShell commands](github-release-commands.md).
Publication targets `v1.0.0` on `dev`, as a full GitHub release of the local
AI engineering platform. The original 400-trial behavioral gate remains **FAIL**.
The opt-in resource guard passed a separately declared, exposed 58-trial
regression at 20/20 clean and 38/38 attacked. No default was promoted.

```sh
# Ubuntu/WSL; installed pinned Node runtime and locked Python environment
make package-check
# A chosen destination must be new; previous package attempts are retained.
make package-check PACKAGE_DIR=artifacts/my-new-v1-package
```

The target builds the real console, a source distribution and a wheel derived
from that source distribution. Console artifacts are included in both archives;
the original wheel-only build rule lost the console when rebuilding from the
source archive. `scripts/check_package.py` inspects both archives, rejects local
runtime directories and installs the wheel in a temporary environment with the
lockfile's exact runtime dependencies. It verifies isolated CLI imports, console
assets and fixture control initialization. It makes zero model calls. Fixture
files still come from the repository; the wheel is not a standalone live setup.

The output contains the wheel, source archive, `RELEASE_NOTES.md` and
`SHA256SUMS.json`. The current verified PC output lives at
`/home/pushy/secure-agent-platform/artifacts/v1-verified-release-package-2026-10-08`.
Later builds use a fresh output path and retain earlier attempts. The upload
bundle is also copied to the Windows checkout at
`artifacts/v1-final-release-assets-2026-10-08`, with the reviewed recording and a
validation manifest. Its SHA-256 manifest covers every upload except itself.

GitHub CI defines contracts/portable evidence/Docker checks, sixteen browser
tests, an actual 64-to-96 MiB storage exhaustion/recovery job, and an installed
package job. It uploads measurement JSON and the package as workflow artifacts.
The YAML and equivalent local commands have been reviewed/exercised; hosted CI
has not run on these changes. There is no automatic public release or inference
study in CI. Builds may access dependency registries; this is not offline-run
evidence.

The [release requirements](release-readiness.md) now include completed storage,
live faults/cancellation/orphan restart cleanup, network observation and the
new candidate regression, with explicit scopes and retained observer failures.
Before publishing, the user reviews the final source/evidence diff, commits and
pushes it, and obtains passing hosted CI. Create a full V1 release with the package and the
reviewed fixture recording. Use the [prepared notes](release-notes.md)
and retain every failed objective. Do not label the exposed templates as an
untouched holdout, change historical grades or claim production readiness.
The prepared package is unpublished until the tagged revision's hosted checks
pass. The agent has not pushed, created a remote tag or published a release.
The public release page is the authoritative publication record after the user
executes those steps.

The first hosted V1 run passed contracts/Docker/portable verification, browser
tests and installed packaging. Its fresh-checkout storage permissions issue is
fixed and [reproduced locally with 18/18 checks](evidence/v1-ci-storage-fix-2026-10-08/README.md).
The corrected hosted run must pass after the user's next push. For publication,
download the `v1-package` artifact from that exact successful run and add the
reviewed video and a new release manifest. This binds the uploaded package to
the tagged source commit without rewriting any earlier local package.
