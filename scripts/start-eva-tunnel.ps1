param(
    [int]$FrontendPort = 3100
)

$ErrorActionPreference = "Stop"
$cloudflared = Join-Path $env:LOCALAPPDATA "CloudflareTunnel\cloudflared.exe"
$runtimeDir = Join-Path $env:LOCALAPPDATA "CloudflareTunnel\eva"
$logFile = Join-Path $runtimeDir "tunnel.log"
$outFile = Join-Path $runtimeDir "tunnel.out"
$errorFile = Join-Path $runtimeDir "tunnel.err"
$pidFile = Join-Path $runtimeDir "tunnel.pid"

if (-not (Test-Path -LiteralPath $cloudflared)) {
    throw "cloudflared is not installed at $cloudflared"
}

$frontend = Get-NetTCPConnection -State Listen -LocalPort $FrontendPort -ErrorAction SilentlyContinue
if (-not $frontend) {
    throw "EVA is not listening on port $FrontendPort. Start EVA before opening the tunnel."
}

New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null

if (Test-Path -LiteralPath $pidFile) {
    $existingPid = Get-Content -LiteralPath $pidFile -ErrorAction SilentlyContinue
    if ($existingPid -and (Get-Process -Id $existingPid -ErrorAction SilentlyContinue)) {
        $existingUrl = Select-String -Path $logFile,$outFile,$errorFile -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" -AllMatches -ErrorAction SilentlyContinue |
            Select-Object -Last 1
        if ($existingUrl) {
            Write-Host "EVA is already public at $($existingUrl.Matches.Value)"
            exit 0
        }
        throw "An EVA tunnel is already running with process ID $existingPid."
    }
}

Remove-Item -LiteralPath $logFile,$outFile,$errorFile,$pidFile -Force -ErrorAction SilentlyContinue
$process = Start-Process -FilePath $cloudflared `
    -ArgumentList @("tunnel", "--url", "http://127.0.0.1:$FrontendPort", "--no-autoupdate", "--logfile", $logFile, "--loglevel", "info") `
    -WindowStyle Hidden `
    -RedirectStandardOutput $outFile `
    -RedirectStandardError $errorFile `
    -PassThru
$process.Id | Set-Content -LiteralPath $pidFile

$publicUrl = $null
for ($attempt = 0; $attempt -lt 60 -and -not $publicUrl; $attempt++) {
    foreach ($file in @($logFile, $outFile, $errorFile)) {
        if (Test-Path -LiteralPath $file) {
            $match = Select-String -Path $file -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" -AllMatches |
                Select-Object -Last 1
            if ($match) {
                $publicUrl = $match.Matches.Value
                break
            }
        }
    }
    if (-not $publicUrl) { Start-Sleep -Milliseconds 500 }
}

if (-not $publicUrl) {
    Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    throw "Cloudflare did not provide a public URL. Review $errorFile"
}

Write-Host "EVA is public at $publicUrl"
Write-Host "Keep this computer, Docker Desktop, EVA, and the tunnel running while others test."
