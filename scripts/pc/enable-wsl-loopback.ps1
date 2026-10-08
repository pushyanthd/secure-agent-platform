$ErrorActionPreference = 'Stop'
$configPath = Join-Path $env:USERPROFILE '.wslconfig'
$configuration = if (Test-Path -LiteralPath $configPath) {
    Get-Content -LiteralPath $configPath -Raw
} else { '' }
if ($configuration -match '(?im)^\s*networkingMode\s*=\s*mirrored\s*$') {
    Write-Output 'Mirrored WSL networking is already configured.'
    exit 0
}
if (Test-Path -LiteralPath $configPath) {
    $backupPath = "$configPath.agentguard-backup-$(Get-Date -Format yyyyMMdd-HHmmss)"
    Copy-Item -LiteralPath $configPath -Destination $backupPath
}
if ($configuration -match '(?im)^\s*networkingMode\s*=') {
    $configuration = [regex]::Replace($configuration, '(?im)^\s*networkingMode\s*=.*$', 'networkingMode=mirrored')
} elseif ($configuration -match '(?im)^\[wsl2\]\s*$') {
    $configuration = [regex]::Replace($configuration, '(?im)^\[wsl2\]\s*$', "[wsl2]`nnetworkingMode=mirrored")
} else {
    $configuration += "`n[wsl2]`nnetworkingMode=mirrored`n"
}
[System.IO.File]::WriteAllText($configPath, $configuration)
Write-Output 'Enabled mirrored networking for loopback-only Windows inference. Restart WSL to apply.'
