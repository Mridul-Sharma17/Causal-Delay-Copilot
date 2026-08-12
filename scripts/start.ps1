[CmdletBinding()]
param(
    [switch]$NoBrowser,
    [switch]$SmokeOnly,
    [switch]$QualificationRun,
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
$serverReady = $false

Push-Location $root
try {
    . (Join-Path $root "scripts\local-fallback-common.ps1")
    if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
        throw "The prepared interpreter is unavailable; run setup.ps1 while online."
    }

    Set-LocalFallbackEnvironment -Root $root -StateRoot $stateRoot -SpaDistDir $spaDistDir
    $env:CORE_REQUIRE_FRESH_DEMO_QUALIFICATION = if ($QualificationRun) { "false" } else { "true" }
    Assert-LocalFallbackNotRunning -StateRoot $stateRoot
    $lifecycleLock = Open-LocalFallbackLifecycleLock -StateRoot $stateRoot
    Invoke-LocalFallbackPythonJson -PythonPath $pythonPath -Arguments @(
        "-m", "backend.app.local_fallback", "preflight"
    ) | Out-Null

    $server = Start-LocalFallbackServer -Root $root -PythonPath $pythonPath
    Write-LocalFallbackProcessMarker -StateRoot $stateRoot -Process $server.Process
    $health = Wait-LocalFallbackReady -Process $server.Process
    Assert-LocalFallbackSpa
    $serverReady = $true

    if ($health.readiness.state -eq "degraded") {
        Write-Host "Causal Delay Copilot is live; Core is ready with Gemini-only drafting unavailable."
    } else {
        Write-Host "Causal Delay Copilot is live and Core is ready."
    }
    if ($SmokeOnly) {
        Write-Host "Local fallback startup smoke passed."
    } else {
        if (-not $NoBrowser) {
            Start-Process "http://127.0.0.1:8000"
        }
        $server.Process.WaitForExit()
        if ($server.Process.ExitCode -ne 0) {
            throw "The local fallback server stopped unexpectedly."
        }
    }
} catch {
    Write-Error $_.Exception.Message
    exit 1
} finally {
    if ($serverReady) {
        Stop-LocalFallbackServer -Server $server -Graceful -StateRoot $stateRoot
    } else {
        Stop-LocalFallbackServer -Server $server
    }
    Remove-LocalFallbackProcessMarker -StateRoot $stateRoot
    Close-LocalFallbackLifecycleLock -LockStream $lifecycleLock
    Pop-Location
}
