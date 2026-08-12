[CmdletBinding()]
param(
    [string]$StateRoot = "state"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ([System.IO.Path]::IsPathRooted($StateRoot)) {
    $stateRoot = [System.IO.Path]::GetFullPath($StateRoot)
} else {
    $stateRoot = [System.IO.Path]::GetFullPath((Join-Path $root $StateRoot))
}
$spaDistDir = Join-Path $root "frontend\dist"
$pythonPath = Join-Path $root ".venv\Scripts\python.exe"
$lifecycleLock = $null
$server = $null

Push-Location $root
try {
    . (Join-Path $root "scripts\local-fallback-common.ps1")

    if ($PSVersionTable.PSVersion.Major -lt 5) {
        throw "Windows PowerShell 5.1 or newer is required."
    }

    $nodeCommand = Get-Command node.exe -ErrorAction SilentlyContinue
    $npmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue
    $uvCommand = Get-Command uv.exe -ErrorAction SilentlyContinue
    if ($null -eq $nodeCommand -or $null -eq $npmCommand -or $null -eq $uvCommand) {
        throw "Node.js, npm, and uv are required before setup can run."
    }

    $nodeVersion = (& $nodeCommand.Source --version).Trim()
    if ($nodeVersion -notmatch '^v(?<major>\d+)\.(?<minor>\d+)\.(?<patch>\d+)') {
        throw "The installed Node.js version is unsupported."
    }
    if ([int]$matches.major -lt 22 -or ([int]$matches.major -eq 22 -and [int]$matches.minor -lt 12)) {
        throw "Node.js 22.12.0 or newer is required."
    }

    $expectedPython = (Get-Content -LiteralPath (Join-Path $root ".python-version") -Raw).Trim()
    if ([string]::IsNullOrWhiteSpace($expectedPython)) {
        throw "The supported Python runtime declaration is missing."
    }
    & uv.exe python find $expectedPython *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "The supported Python runtime is unavailable."
    }

    & npm.cmd ci --ignore-scripts --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) {
        throw "Locked npm installation failed; setup success was not recorded."
    }
    & uv.exe sync --locked
    if ($LASTEXITCODE -ne 0) {
        throw "Locked Python installation failed; setup success was not recorded."
    }

    if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
        throw "The prepared virtual-environment interpreter is missing."
    }
    $pythonVersion = (& $pythonPath --version 2>&1).Trim()
    if ($pythonVersion -notmatch [regex]::Escape($expectedPython)) {
        throw "The prepared Python runtime does not match .python-version."
    }

    $env:PLAYWRIGHT_BROWSERS_PATH = "0"
    $playwrightCommand = Join-Path $root "node_modules\.bin\playwright.cmd"
    if (-not (Test-Path -LiteralPath $playwrightCommand -PathType Leaf)) {
        throw "The lockfile-resolved Playwright CLI is unavailable; setup success was not recorded."
    }
    & $playwrightCommand install chromium
    if ($LASTEXITCODE -ne 0) {
        throw "Pinned Playwright Chromium installation failed; setup success was not recorded."
    }
    & npm.cmd run typecheck
    if ($LASTEXITCODE -ne 0) {
        throw "Frontend typechecking failed; setup success was not recorded."
    }
    & npm.cmd test
    if ($LASTEXITCODE -ne 0) {
        throw "Frontend tests failed; setup success was not recorded."
    }
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) {
        throw "The SPA build failed; setup success was not recorded."
    }

    Set-LocalFallbackEnvironment -Root $root -StateRoot $stateRoot -SpaDistDir $spaDistDir
    $env:CORE_REQUIRE_FRESH_DEMO_QUALIFICATION = "false"
    & $pythonPath -c "from backend.app.main import create_app; print('backend import smoke passed')"
    if ($LASTEXITCODE -ne 0) {
        throw "Backend import smoke failed; setup success was not recorded."
    }
    Invoke-LocalFallbackPythonJson -PythonPath $pythonPath -Arguments @("-m", "backend.app.local_fallback", "initialize") | Out-Null

    Assert-LocalFallbackNotRunning -StateRoot $stateRoot
    $lifecycleLock = Open-LocalFallbackLifecycleLock -StateRoot $stateRoot
    $server = Start-LocalFallbackServer -Root $root -PythonPath $pythonPath
    Write-LocalFallbackProcessMarker -StateRoot $stateRoot -Process $server.Process
    $null = Wait-LocalFallbackReady -Process $server.Process
    Assert-LocalFallbackSpa
    & $playwrightCommand test tests/e2e/health.spec.ts --config playwright.config.ts --workers=1
    if ($LASTEXITCODE -ne 0) {
        throw "Packaged browser smoke failed; setup success was not recorded."
    }
    Stop-LocalFallbackServer -Server $server
    $server = $null
    Remove-LocalFallbackProcessMarker -StateRoot $stateRoot
    Close-LocalFallbackLifecycleLock -LockStream $lifecycleLock
    $lifecycleLock = $null

    Invoke-LocalFallbackPythonJson -PythonPath $pythonPath -Arguments @(
        "-m", "backend.app.local_fallback", "record-setup-success", "--node-version", $nodeVersion
    ) | Out-Null
    Write-Host "Local fallback setup succeeded. Run .\scripts\start.ps1 while offline."
} catch {
    Write-Error $_.Exception.Message
    exit 1
} finally {
    Stop-LocalFallbackServer -Server $server
    Remove-LocalFallbackProcessMarker -StateRoot $stateRoot
    Close-LocalFallbackLifecycleLock -LockStream $lifecycleLock
    Pop-Location
}
