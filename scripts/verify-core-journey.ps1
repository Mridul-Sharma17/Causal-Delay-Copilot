[CmdletBinding()]
param(
    [int]$Port = 8787
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$uvExecutable = (Get-Command uv -ErrorAction Stop).Source
$uvCacheDir = Join-Path $repoRoot ".uv-cache"
$playwrightExecutable = Join-Path $repoRoot "node_modules\.bin\playwright.cmd"
$npmExecutable = (Get-Command npm.cmd -ErrorAction Stop).Source

if (-not (Test-Path -LiteralPath $playwrightExecutable -PathType Leaf)) {
    throw "Repository-local Playwright CLI is unavailable: $playwrightExecutable"
}
if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
    throw "The verification port is already in use: $Port"
}

$taskTempRoot = Join-Path $repoRoot ".tmp"
New-Item -ItemType Directory -Force -Path $taskTempRoot | Out-Null
$runId = Get-Date -Format "yyyyMMddHHmmssfff"
$runRoot = Join-Path $taskTempRoot "core-journey-$runId"
$tempRoot = Join-Path $runRoot "temp"
$pytestBase = Join-Path $tempRoot "pytest-basetemp"
$stateRoot = Join-Path $runRoot "state"
New-Item -ItemType Directory -Path $runRoot | Out-Null
New-Item -ItemType Directory -Path $tempRoot | Out-Null
New-Item -ItemType Directory -Path $stateRoot | Out-Null
$env:TEMP = $tempRoot
$env:TMP = $tempRoot
$env:CORE_GEMINI_ENABLED = "false"
$env:CORE_GEMINI_API_KEY = ""

function Invoke-Checked {
    param(
        [string]$Label,
        [scriptblock]$Command
    )

    Write-Host "==> $Label"
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

Invoke-Checked "TypeScript typecheck" {
    & $npmExecutable run typecheck
}
Invoke-Checked "Frontend unit tests" {
    & $npmExecutable test
}
Invoke-Checked "Python unit, contract, integration, operational, and evaluation tests" {
    & $uvExecutable --cache-dir (Join-Path $repoRoot ".uv-cache") run --locked --no-sync pytest --basetemp $pytestBase
}
Invoke-Checked "Compiled SPA build" {
    & $npmExecutable run build
}

$origin = "http://127.0.0.1:$Port"
Invoke-Checked "Real API journey preparation" {
    & $uvExecutable --cache-dir (Join-Path $repoRoot ".uv-cache") run --locked --no-sync python -m scripts.prepare_core_journey `
        --state-root $stateRoot `
        --profile LOCAL_FALLBACK `
        --public-origin $origin `
        --spa-dist-dir (Join-Path $repoRoot "frontend\dist")
}

$env:CORE_PROFILE = "LOCAL_FALLBACK"
$env:CORE_STATE_ROOT = $stateRoot
$env:CORE_PUBLIC_ORIGIN = $origin
$env:CORE_BIND_HOST = "127.0.0.1"
$env:CORE_OFFLINE_STARTUP = "true"
$env:CORE_RELEASE_CANDIDATE_ID = "core-issue-64-local_fallback"
$env:CORE_BUILD_MANIFEST_ID = "core-issue-64-browser-v1"
$env:CORE_GEMINI_ENABLED = "false"
$env:CORE_GEMINI_API_KEY = ""
$env:CORE_SPA_DIST_DIR = Join-Path $repoRoot "frontend\dist"
$env:CORE_E2E_BASE_URL = $origin

$serverOutput = Join-Path $stateRoot "server.stdout.log"
$serverError = Join-Path $stateRoot "server.stderr.log"
$serverProcess = $null

try {
    $serverProcess = Start-Process `
        -FilePath $uvExecutable `
        -ArgumentList @(
            "--cache-dir", ('"{0}"' -f $uvCacheDir),
            "run", "--locked", "--no-sync", "uvicorn", "backend.app.main:app",
            "--host", "127.0.0.1", "--port", [string]$Port, "--workers", "1"
        ) `
        -WorkingDirectory $repoRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $serverOutput `
        -RedirectStandardError $serverError `
        -PassThru

    $ready = $false
    for ($attempt = 0; $attempt -lt 120; $attempt++) {
        if ($serverProcess.HasExited) {
            break
        }
        try {
            $probe = Invoke-WebRequest -UseBasicParsing -Uri "$origin/api/health/ready" -TimeoutSec 2
            if ($probe.StatusCode -eq 200) {
                $ready = $true
                break
            }
        } catch {
            # The server is still starting; keep the bounded readiness wait.
        }
        Start-Sleep -Milliseconds 500
    }
    if (-not $ready) {
        $stderr = if (Test-Path -LiteralPath $serverError) {
            Get-Content -LiteralPath $serverError -Raw
        } else {
            "No server stderr was captured."
        }
        throw "Packaged Core did not become ready. $stderr"
    }

    Invoke-Checked "Repository-local Playwright compiled-browser seam" {
        & $playwrightExecutable test tests/e2e/core_journey.spec.ts --config playwright.config.ts --workers=1
    }
} finally {
    $serverProcessIds = @()
    if ($null -ne $serverProcess) {
        $serverProcessIds += $serverProcess.Id
    }
    $serverProcessIds += @(
        Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
            Where-Object {
                $_.CommandLine -and
                $_.CommandLine.Contains($repoRoot) -and
                $_.CommandLine.Contains("backend.app.main:app") -and
                $_.CommandLine.Contains("--port $Port")
            } |
            Select-Object -ExpandProperty ProcessId
    )
    foreach ($processId in ($serverProcessIds | Sort-Object -Unique)) {
        Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "CORE_JOURNEY_VERIFIED state_root=$stateRoot origin=$origin"
