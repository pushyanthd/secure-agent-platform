# Publish V1 yourself

The agent fixed and reproduced the storage CI permissions issue locally. It did
not push, tag, merge or publish. Run these PowerShell commands yourself; the same
commands are provided directly in the chat. No administrator window is needed.

They require all four jobs to pass on the exact release commit, download that
run's package and storage artifacts, preserve original downloaded checksums,
and publish a normal V1 release with the reviewed fixture video and fresh asset
checksums. Only allowlisted root files are uploaded; downloaded raw controller
reports remain private in ignored subdirectories.

The final PR updates the default branch's README and preserves dev. Inspect its
checks before merging. If v1.0.0 or a release PR already exists, stop and inspect
it; do not overwrite the version or create a duplicate PR. If no PR checks are
reported immediately, repeat the checks command once they are registered.

```powershell
$ErrorActionPreference = 'Stop'
Set-Location 'C:\Users\pushy\OneDrive\Desktop\Code\github-projects\secure-agent-platform'

function Invoke-Git {
    & git @args
    if ($LASTEXITCODE -ne 0) { throw 'Git failed; stop and inspect its output.' }
}
function Invoke-Gh {
    & wsl.exe -d Ubuntu -- gh @args
    if ($LASTEXITCODE -ne 0) { throw 'GitHub CLI failed; stop and inspect its output.' }
}
$repo = 'pushyanthd/secure-agent-platform'
if ((Invoke-Git branch --show-current).Trim() -ne 'dev') { throw 'Expected branch dev.' }
Invoke-Git diff --check
Invoke-Git add .github/workflows/ci.yml docs/artifact-storage.md docs/release-packaging.md docs/github-release-commands.md docs/evidence/v1-ci-storage-fix-2026-10-08
Invoke-Git commit -m 'Fix fresh-checkout storage CI permissions'
$releaseCommit = (Invoke-Git rev-parse HEAD).Trim()
Invoke-Git push origin dev

& wsl.exe -d Ubuntu -- gh auth status
if ($LASTEXITCODE -ne 0) {
    Invoke-Gh auth login --hostname github.com --git-protocol https --web
}
$deadline = (Get-Date).AddMinutes(5)
$runId = $null
while (-not $runId -and (Get-Date) -lt $deadline) {
    $runs = Invoke-Gh run list --repo $repo --branch dev --commit $releaseCommit --workflow ci.yml --event push --limit 1 --json databaseId | ConvertFrom-Json
    $runId = $runs.databaseId
    if (-not $runId) { Start-Sleep -Seconds 5 }
}
if (-not $runId) { throw 'No CI run appeared. Stop before tagging.' }
Invoke-Gh run watch $runId --repo $repo --exit-status
$ci = Invoke-Gh api "repos/$repo/actions/runs/$runId" | ConvertFrom-Json
if ($ci.head_sha -ne $releaseCommit -or $ci.conclusion -ne 'success') { throw 'Exact release commit has not passed CI.' }
$jobs = (Invoke-Gh api "repos/$repo/actions/runs/$runId/jobs?per_page=100" | ConvertFrom-Json).jobs
foreach ($expected in @('contracts', 'operator-ui', 'artifact-storage', 'package')) {
    if (@($jobs | Where-Object { $_.name -eq $expected -and $_.conclusion -eq 'success' }).Count -ne 1) {
        throw "Required CI job did not pass: $expected"
    }
}

$bundleName = 'v1.0.0-release-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
$assets = Join-Path (Get-Location) "artifacts\$bundleName"
$wslAssets = '/mnt/c/Users/pushy/OneDrive/Desktop/Code/github-projects/secure-agent-platform/artifacts/' + $bundleName
$utf8 = [System.Text.UTF8Encoding]::new($false)
New-Item -ItemType Directory -Path $assets | Out-Null
Invoke-Gh run download $runId --repo $repo --name v1-package --dir "$wslAssets/ci-package"
Invoke-Gh run download $runId --repo $repo --name authored-storage-measurement --dir "$wslAssets/ci-storage"
$package = Join-Path $assets 'ci-package'
$packageHashes = Get-Content "$package\SHA256SUMS.json" -Raw | ConvertFrom-Json
foreach ($entry in $packageHashes.PSObject.Properties) {
    $actual = (Get-FileHash -LiteralPath (Join-Path $package $entry.Name) -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $entry.Value) { throw "CI package checksum mismatch: $($entry.Name)" }
}
foreach ($name in @('agentguard-1.0.0-py3-none-any.whl', 'agentguard-1.0.0.tar.gz')) {
    Copy-Item -LiteralPath (Join-Path $package $name) -Destination $assets
}
$prepared = Join-Path (Get-Location) 'artifacts\v1-final-release-assets-2026-10-08'
Copy-Item -LiteralPath "$prepared\RELEASE_NOTES.md" -Destination $assets
Copy-Item -LiteralPath "$prepared\v1-walkthrough.webm" -Destination $assets
$prior = Get-Content "$prepared\RELEASE_MANIFEST.json" -Raw | ConvertFrom-Json
$storage = Get-Content "$assets\ci-storage\report.json" -Raw | ConvertFrom-Json
if (-not $storage.passed -or @($storage.checks.PSObject.Properties | Where-Object { $_.Value -ne $true }).Count) {
    throw 'Hosted storage measurement did not pass every check.'
}
$storageSummary = [ordered]@{ mode = $storage.mode; fresh_model_calls = $storage.fresh_model_calls; checks = $storage.checks; passed = $storage.passed }
[System.IO.File]::WriteAllText("$assets\STORAGE_CHECKS.json", ($storageSummary | ConvertTo-Json -Depth 10), $utf8)
$manifest = [ordered]@{
    release = 'v1.0.0'; source_commit = $releaseCommit
    hosted_ci = [ordered]@{ run_id = $runId; url = $ci.html_url; conclusion = $ci.conclusion }
    ci_package_checksums = $packageHashes
    candidate_regression = $prior.candidate_regression
    recording = $prior.recording
    runtime_source_sha256 = $prior.local_validation.runtime_source_sha256
    storage_checks_passed = @($storage.checks.PSObject.Properties).Count
}
[System.IO.File]::WriteAllText("$assets\RELEASE_MANIFEST.json", ($manifest | ConvertTo-Json -Depth 15), $utf8)
$hashes = [ordered]@{}
Get-ChildItem -LiteralPath $assets -File | Sort-Object Name | ForEach-Object {
    $hashes[$_.Name] = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
}
[System.IO.File]::WriteAllText("$assets\SHA256SUMS.json", ($hashes | ConvertTo-Json), $utf8)
if ((Invoke-Git rev-parse HEAD).Trim() -ne $releaseCommit -or (Invoke-Git status --porcelain)) { throw 'Source changed after CI.' }
Invoke-Git tag -a v1.0.0 $releaseCommit -m 'Secure Agent Platform V1'
Invoke-Git push origin v1.0.0
$uploadPaths = @(Get-ChildItem -LiteralPath $assets -File | ForEach-Object { "$wslAssets/$($_.Name)" })
Invoke-Gh release create v1.0.0 @uploadPaths --repo $repo --verify-tag --title 'Secure Agent Platform V1' --notes-file "$wslAssets/RELEASE_NOTES.md" --latest
Invoke-Gh release view v1.0.0 --repo $repo

# Make the V1 README visible on the default branch; keep dev.
Invoke-Gh pr create --repo $repo --base main --head dev --title 'Ship Secure Agent Platform V1' --body-file "$wslAssets/RELEASE_NOTES.md"
Start-Sleep -Seconds 10
Invoke-Gh pr checks dev --repo $repo --watch
Invoke-Gh pr merge dev --repo $repo --merge

```
