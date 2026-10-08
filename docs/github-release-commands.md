# Publish V1 yourself

The agent prepared the local release and did not push, create a remote tag or
publish a release. These commands perform all GitHub activity under your control.
Run them in PowerShell. The GitHub CLI is already installed in Ubuntu WSL;
Windows Git uses your existing credential manager. No administrator window is needed.

## Review, commit and push the source

```powershell
Set-Location 'C:\Users\pushy\OneDrive\Desktop\Code\github-projects\secure-agent-platform'
git status --short
git diff --check
git add --all
git commit -m "Ship V1 local agent platform and measured release evidence"
if ($LASTEXITCODE -ne 0) { throw 'Commit failed; inspect the output.' }
$releaseCommit = (git rev-parse HEAD).Trim()
git push origin dev
if ($LASTEXITCODE -ne 0) { throw 'Push failed; inspect the output.' }
```

Only commit the intended source and evidence. Local databases, credentials,
model weights and release assets are ignored. The original frozen evidence
is retained. This does not merge `dev` into `main`.

## Authenticate and wait for the exact commit's CI

```powershell
function Invoke-PortfolioGh {
    & wsl.exe -d Ubuntu -- gh @args
    if ($LASTEXITCODE -ne 0) { throw 'GitHub CLI failed; inspect the output.' }
}
$githubRepository = 'pushyanthd/secure-agent-platform'
Invoke-PortfolioGh auth login --hostname github.com --git-protocol https --web

$deadline = (Get-Date).AddMinutes(5)
$runId = ''
while (-not $runId -and (Get-Date) -lt $deadline) {
    $runId = (Invoke-PortfolioGh run list --repo $githubRepository --branch dev --commit $releaseCommit --workflow ci.yml --event push --limit 1 --json databaseId --jq '.[0].databaseId' | Out-String).Trim()
    if (-not $runId) { Start-Sleep -Seconds 5 }
}
if (-not $runId) { throw 'No CI run found. Check the Actions tab before continuing.' }
Invoke-PortfolioGh run watch $runId --repo $githubRepository --exit-status
$ciResult = Invoke-PortfolioGh api "repos/$githubRepository/actions/runs/$runId" | ConvertFrom-Json
if ($ciResult.head_sha -ne $releaseCommit -or $ciResult.conclusion -ne 'success') {
    throw 'The exact release commit has not passed hosted CI.'
}
```

Authentication is unnecessary if `gh auth status` already succeeds. All four
jobs must pass: contracts/Docker/portable outcomes, operator UI, real artifact
storage and installed package. If a job fails, stop before tagging and retain
the failed run. Fix the concrete problem and repeat with the new source commit.

## Verify local assets, tag and publish a normal V1 release

```powershell
$assetDirectory = Join-Path (Get-Location) 'artifacts\v1-final-release-assets-2026-10-08'
$checksums = Get-Content (Join-Path $assetDirectory 'SHA256SUMS.json') -Raw | ConvertFrom-Json
foreach ($entry in $checksums.PSObject.Properties) {
    $actual = (Get-FileHash -LiteralPath (Join-Path $assetDirectory $entry.Name) -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $entry.Value) { throw "Checksum mismatch: $($entry.Name)" }
}
if ((git rev-parse HEAD).Trim() -ne $releaseCommit) { throw 'Source changed after CI.' }
if (git status --porcelain) { throw 'Working tree changed after CI.' }
git tag -a v1.0.0 $releaseCommit -m "Secure Agent Platform V1"
if ($LASTEXITCODE -ne 0) { throw 'Tag creation failed. Do not overwrite an existing tag.' }
git push origin v1.0.0
if ($LASTEXITCODE -ne 0) { throw 'Tag push failed.' }

$wslAssetDirectory = '/mnt/c/Users/pushy/OneDrive/Desktop/Code/github-projects/secure-agent-platform/artifacts/v1-final-release-assets-2026-10-08'
$assetPaths = @(Get-ChildItem -LiteralPath $assetDirectory -File | ForEach-Object { "$wslAssetDirectory/$($_.Name)" })
Invoke-PortfolioGh release create v1.0.0 @assetPaths --repo $githubRepository --verify-tag --title 'Secure Agent Platform V1' --notes-file "$wslAssetDirectory/RELEASE_NOTES.md" --latest
Invoke-PortfolioGh release view v1.0.0 --repo $githubRepository
```

This creates a normal release, with no prerelease flag, at the CI-verified
`dev` commit. The assets include the 1.0.0 wheel, source distribution, release
notes, reviewed fixture walkthrough, validation manifest and SHA-256 checksums.
Frozen experimental protocol names and prior grades inside the evidence remain
unchanged. The public release page and Actions run become the publication record.

If release creation fails after the tag push, keep the tag and fix the reported
problem. Do not rerun tag creation or overwrite the immutable version. Inspect
`gh release view` before attempting a release retry. No GitHub publication is
claimed by the local preparation record.

## Optional: make V1 visible on the repository's main page

The repository's default branch is `main`; publishing a tag from `dev` does
not update its front-page README. To present the V1 story on the default branch,
open and merge a PR yourself after reviewing its changes and passing checks:

```powershell
Invoke-PortfolioGh pr create --repo $githubRepository --base main --head dev --title 'Ship Secure Agent Platform V1' --body-file "$wslAssetDirectory/RELEASE_NOTES.md"
Invoke-PortfolioGh pr checks dev --repo $githubRepository --watch
Invoke-PortfolioGh pr merge dev --repo $githubRepository --merge
```

This preserves the `dev` branch and existing historical evidence. If an open
PR already exists, inspect it instead of creating a duplicate. A normal merge
keeps the tagged release commit in history; do not force-push or move `v1.0.0`.
