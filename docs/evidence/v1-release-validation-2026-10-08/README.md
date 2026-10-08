# V1 release validation

The final V1 source is checked in the documented Ubuntu/WSL environment:
Python contracts, lint, formatting, strict types, the real console build,
browser behavior and installation of the 1.0.0 wheel rebuilt from its source
archive. Validation uses authored fixtures and makes zero model calls.

Final local checks passed **826 Python tests**, lint, formatting and strict
types, plus the console build/check and **16 browser tests**. Their complete
logs are retained here. Package installation results and asset checksums are
published alongside the completed local package. Hosted CI is pending the
user's push and is not claimed by this publication.

Portable verification separately checks all 446 published PC outcomes,
including the 58-trial candidate regression. The retained earlier
[local snapshot](../experimental-v1-validation-2026-10-08/README.md) records
826 Python tests and the pre-branding 0.1.0 package; historical publications
remain unchanged. This is the same PC environment, not external reproduction.

The release workflow adds hosted contracts, portable grades, Docker probes,
sixteen browser tests, real storage exhaustion/recovery and installed-package
checks. Its public run and source commit identify the hosted result. Build and
installation may use dependency registries; the measured inference network
evidence is a separate publication.
