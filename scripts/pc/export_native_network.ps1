param([Parameter(Mandatory=$true)][string]$ObservationDirectory)
$ErrorActionPreference = 'Stop'
$directory = [IO.Path]::GetFullPath($ObservationDirectory)
if (-not (Test-Path -LiteralPath (Join-Path $directory 'observation.json'))) { throw 'Stop observation before exporting' }
if (Test-Path -LiteralPath (Join-Path $directory 'events.csv')) { throw 'Preserve existing extraction' }
$schemas = @{}
foreach ($definition in (Get-WinEvent -ListProvider Microsoft-Windows-TCPIP).Events) {
    if (-not $definition.Template) { continue }
    [xml]$template = $definition.Template
    $schemas["$($definition.Id):$($definition.Version)"] = @($template.template.data | ForEach-Object { $_.name })
}
$schemas | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $directory 'provider-schemas.json') -Encoding UTF8
# Native tracerpt is faster than formatting every host event with Get-WinEvent.
# Full-host CSV stays private. Python extracts only model-owned observations,
# using owning process payload fields as well as event-header process context.
& tracerpt.exe (Join-Path $directory 'network.etl') -o (Join-Path $directory 'events.csv') -of CSV -y -summary (Join-Path $directory 'trace-summary.txt')
if ($LASTEXITCODE -ne 0) { throw 'Trace decode failed' }
Write-Host 'Private CSV, event-loss summary and provider schemas retained for model extraction.'
