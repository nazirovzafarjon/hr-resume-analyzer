<#
.SYNOPSIS
    Open (or close) public test access to the local stack through ngrok.

.DESCRIPTION
    up      Builds and starts the stack with docker-compose.public.yml: the CRM,
            the API and the Telegram bot become reachable at https://<NGROK_DOMAIN>
            while this machine keeps running.
    down    Removes the public services (ngrok, edge, crm) and restarts the
            backend with its local settings again.
    status  Shows the public containers and the URL ngrok is serving.
    logs    Follows the ngrok and edge logs.

    Needs NGROK_AUTHTOKEN and NGROK_DOMAIN in the root .env file.
    See docs/operations/PUBLIC_TEST_ACCESS.md.

.EXAMPLE
    .\scripts\public.ps1 up
.EXAMPLE
    .\scripts\public.ps1 up -NoBot
.EXAMPLE
    .\scripts\public.ps1 down
#>
param(
    [ValidateSet("up", "down", "status", "logs")]
    [string]$Action = "up",
    # Start without the Telegram bot (it is on by default).
    [switch]$NoBot
)

# No "Stop" preference: docker compose prints progress on stderr, which some
# hosts turn into errors. Exit codes are checked explicitly instead.
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Get-DotEnvValue([string]$name) {
    # Compose gives the shell environment priority over .env; do the same.
    $fromShell = [Environment]::GetEnvironmentVariable($name)
    if ($fromShell) { return $fromShell.Trim() }
    $envFile = Join-Path $root ".env"
    if (-not (Test-Path $envFile)) { return "" }
    foreach ($line in Get-Content $envFile) {
        if ($line -match "^\s*$name\s*=\s*(.*)$") {
            return $Matches[1].Trim().Trim('"').Trim("'")
        }
    }
    return ""
}

function Assert-PublicConfig {
    $token = Get-DotEnvValue "NGROK_AUTHTOKEN"
    $domain = Get-DotEnvValue "NGROK_DOMAIN"
    $missing = @()
    if (-not $token) { $missing += "NGROK_AUTHTOKEN" }
    if (-not $domain) { $missing += "NGROK_DOMAIN" }
    if ($missing.Count -gt 0) {
        Write-Host "Missing in .env: $($missing -join ', ')" -ForegroundColor Red
        Write-Host "Get both from https://dashboard.ngrok.com (Your Authtoken, Domains)."
        Write-Host "See docs/operations/PUBLIC_TEST_ACCESS.md"
        exit 1
    }
    if ($domain -match "://|/") {
        Write-Host "NGROK_DOMAIN must be the bare host, e.g. my-name.ngrok-free.app (no https://, no slash)." -ForegroundColor Red
        exit 1
    }
    return $domain
}

$profileArgs = @()
if (-not $NoBot) { $profileArgs = @("--profile", "telegram") }
$publicFiles = @("-f", "docker-compose.yml", "-f", "docker-compose.public.yml")

switch ($Action) {
    "up" {
        $domain = Assert-PublicConfig
        docker compose @publicFiles @profileArgs up -d --build
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

        # The ngrok agent reports its endpoint on the local inspector API.
        $online = $false
        for ($i = 0; $i -lt 30 -and -not $online; $i++) {
            try {
                $tunnels = Invoke-RestMethod -Uri "http://127.0.0.1:4040/api/tunnels" -TimeoutSec 2
                $online = @($tunnels.tunnels | Where-Object { $_.public_url -like "*$domain*" }).Count -gt 0
            } catch { }
            if (-not $online) { Start-Sleep -Seconds 1 }
        }

        Write-Host ""
        if ($online) {
            Write-Host "Public URL : https://$domain" -ForegroundColor Green
        } else {
            Write-Host "ngrok is not online yet. Check: .\scripts\public.ps1 logs" -ForegroundColor Yellow
        }
        $edgePort = Get-DotEnvValue "PUBLIC_EDGE_PORT"
        if (-not $edgePort) { $edgePort = "8090" }
        Write-Host "Local check: http://localhost:$edgePort"
        Write-Host "Inspector  : http://localhost:4040"
        Write-Host "Stop       : .\scripts\public.ps1 down"
    }
    "down" {
        # Only the base file: --remove-orphans drops ngrok, edge and crm, and the
        # backend containers are recreated with their local FRONTEND_BASE_URL.
        docker compose @profileArgs up -d --remove-orphans
        exit $LASTEXITCODE
    }
    "status" {
        docker compose @publicFiles @profileArgs ps ngrok edge crm
        try {
            $tunnels = Invoke-RestMethod -Uri "http://127.0.0.1:4040/api/tunnels" -TimeoutSec 2
            $tunnels.tunnels | ForEach-Object { Write-Host "Public URL: $($_.public_url) -> $($_.config.addr)" }
        } catch {
            Write-Host "ngrok inspector is not reachable (public access is off)." -ForegroundColor Yellow
        }
    }
    "logs" {
        docker compose @publicFiles @profileArgs logs -f --tail 100 ngrok edge
    }
}
