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

Push-Location $root
try {
    . (Join-Path $root "scripts\local-fallback-common.ps1")
    $process = Get-LocalFallbackProcessFromMarker -StateRoot $stateRoot
    if ($null -eq $process) {
        Write-Host "No local fallback process is running."
        exit 0
    }

    $stopResult = Request-LocalFallbackStop
    if ($stopResult.outcome -eq "STOP_FAILED") {
        throw "The local fallback reported that safe stop could not be completed."
    }
    if (-not $process.HasExited) {
        $process.Kill()
        $process.WaitForExit()
    }
    Remove-LocalFallbackProcessMarker -StateRoot $stateRoot
    Write-Host ("Local fallback stop completed: {0}." -f $stopResult.outcome)
} catch {
    Write-Error $_.Exception.Message
    exit 1
} finally {
    Pop-Location
}
