$runtimeDir = Join-Path $env:LOCALAPPDATA "CloudflareTunnel\eva"
$pidFile = Join-Path $runtimeDir "tunnel.pid"

if (-not (Test-Path -LiteralPath $pidFile)) {
    Write-Host "No EVA tunnel PID was found."
    exit 0
}

$tunnelPid = Get-Content -LiteralPath $pidFile -ErrorAction SilentlyContinue
if ($tunnelPid -and (Get-Process -Id $tunnelPid -ErrorAction SilentlyContinue)) {
    Stop-Process -Id $tunnelPid
    Write-Host "EVA tunnel stopped."
} else {
    Write-Host "The recorded EVA tunnel is no longer running."
}

Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
