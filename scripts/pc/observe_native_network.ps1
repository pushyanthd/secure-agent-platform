#Requires -RunAsAdministrator
param(
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [int]$MaximumSeconds = 1800
)
$ErrorActionPreference = 'Stop'
if ($MaximumSeconds -lt 60 -or $MaximumSeconds -gt 7200) { throw 'Invalid observation duration' }
$outputPath = [IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $outputPath) { throw 'Preserve existing evidence; choose a fresh directory' }
$models = @(Get-CimInstance Win32_Process -Filter "Name = 'llama-server.exe'")
if ($models.Count -ne 1) { throw 'Exactly one native model process must be running' }
$model = $models[0]
New-Item -ItemType Directory -Path $outputPath | Out-Null
$metadata = @{ schema_version=1; model_pid=$model.ProcessId; executable=$model.ExecutablePath;
    command_line=$model.CommandLine; start_utc=(Get-Date).ToUniversalTime().ToString('o');
    scope='Windows TCPIP ETW observation; full host trace remains private, extract model events before publication' }
$tracePath = Join-Path $outputPath 'network.etl'
$started = $false
try {
    & netsh trace start capture=no report=disabled persistent=no correlation=no provider=Microsoft-Windows-TCPIP level=5 keywords=0xffffffffffffffff filemode=single maxsize=512 "tracefile=$tracePath"
    if ($LASTEXITCODE -ne 0) { throw 'Trace could not start; do not claim measured offline behavior' }
    $started = $true
    $metadata | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $outputPath 'ready.json') -Encoding UTF8
    Write-Host "Native model PID $($model.ProcessId) is observed. Create stop.txt in $outputPath after the WSL run."
    $deadline = (Get-Date).AddSeconds($MaximumSeconds)
    while (-not (Test-Path -LiteralPath (Join-Path $outputPath 'stop.txt')) -and (Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 250
    }
} finally {
    if ($started) {
        & netsh trace stop
        if ($LASTEXITCODE -ne 0) { throw 'Trace stop failed; observation is incomplete' }
        $metadata.end_utc = (Get-Date).ToUniversalTime().ToString('o')
        $metadata.trace_sha256 = (Get-FileHash -LiteralPath $tracePath -Algorithm SHA256).Hash.ToLowerInvariant()
        $metadata | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $outputPath 'observation.json') -Encoding UTF8
        Write-Host 'Trace retained. Review coverage, event loss and process attribution before making an offline claim.'
    }
}
