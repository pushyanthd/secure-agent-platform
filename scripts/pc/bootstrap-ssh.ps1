# Run once in an elevated Windows PowerShell window, as the intended PC administrator.
# Based on Microsoft's Windows OpenSSH installation and key-management documentation.
# Existing authorized keys are preserved. No model HTTP port is opened.
#Requires -RunAsAdministrator
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^ssh-ed25519 [A-Za-z0-9+/=]+(?: [^\r\n]+)?$')]
    [string]$PublicKey
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if (-not (Get-NetConnectionProfile | Where-Object NetworkCategory -eq 'Private')) {
    throw 'Set your trusted home LAN to Private in Windows Network settings, then rerun.'
}
$capability = Get-WindowsCapability -Online -Name 'OpenSSH.Server~~~~0.0.1.0'
if ($capability.State -ne 'Installed') {
    Add-WindowsCapability -Online -Name 'OpenSSH.Server~~~~0.0.1.0' | Out-Null
}
$ruleName = 'OpenSSH-Server-In-TCP'
if (Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue) {
    Set-NetFirewallRule -Name $ruleName -Enabled True -Profile Private -RemoteAddress LocalSubnet
} else {
    New-NetFirewallRule -Name $ruleName -DisplayName 'OpenSSH Server (home LAN)' `
        -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22 `
        -Profile Private -RemoteAddress LocalSubnet | Out-Null
}

$keyPath = Join-Path $env:ProgramData 'ssh\administrators_authorized_keys'
New-Item -ItemType Directory -Force (Split-Path $keyPath) | Out-Null
if (-not (Test-Path $keyPath)) { New-Item -ItemType File $keyPath | Out-Null }
$existing = @(Get-Content $keyPath)
if ($existing -notcontains $PublicKey) { Add-Content -Encoding ascii $keyPath ("`r`n" + $PublicKey) }
& icacls.exe $keyPath /inheritance:r /grant '*S-1-5-32-544:F' /grant '*S-1-5-18:F' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Could not restrict the SSH authorized-key ACL.' }
Set-Service sshd -StartupType Automatic
Start-Service sshd

Write-Output ('SSH user: ' + $env:USERNAME)
Get-NetIPConfiguration | Where-Object IPv4DefaultGateway | ForEach-Object {
    Write-Output ('LAN address: ' + $_.IPv4Address.IPAddress)
}
Write-Output 'Host key fingerprint (verify this from the Mac):'
& "$env:WINDIR\System32\OpenSSH\ssh-keygen.exe" -lf "$env:ProgramData\ssh\ssh_host_ed25519_key.pub"
Write-Output 'GPU inventory:'
& nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
