# Final V1 package validation

The final source archive includes the completed portfolio docs and user-managed
GitHub release instructions. It is compared byte-for-byte with the source files
present in the archive, then its rebuilt wheel is installed and exercised in an
isolated environment. Package hashes and the installation report are recorded
after building; that audit record accompanies the archives in GitHub evidence
and the local release upload bundle.

The unchanged runtime has passed **826 Python tests**, lint, formatting, strict
types and all **16 browser tests**. The retained logs and nine portable verifier
reports cover **446 outcomes**: 388 historical and 58 newly declared candidate
outcomes. Packaging and verification make zero fresh model calls.

Earlier [1.0.0 preparation](../v1-release-validation-2026-10-08/README.md) and
[0.1.0 validation](../experimental-v1-validation-2026-10-08/README.md) remain
available with their original package hashes. The final build supersedes the
earlier archive's documentation snapshot without changing runtime or grades.

Hosted CI and GitHub publication remain user-managed and unverified until the
provided commands are executed. These checks use the same retained Ubuntu/WSL
environment, not independent external reproduction. Build/install may access
dependency registries; measured inference network evidence is separate.

The committed-byte audit checked 1,122 historical evidence files and restored
646 text checkout files from Windows CRLF to their exact committed LF bytes.
Original checkout copies and their hashes are retained privately. Historical
results, grading state, frozen sources and checksum values were not edited.
Frozen publication bytes are excluded from text conversion during WSL sync.
