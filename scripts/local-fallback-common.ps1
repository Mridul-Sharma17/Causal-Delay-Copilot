$ErrorActionPreference = "Stop"

function Set-LocalFallbackEnvironment {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$StateRoot,
        [Parameter(Mandatory = $true)][string]$SpaDistDir
    )

    $origin = "http://127.0.0.1:8000"
    $env:CORE_PROFILE = "LOCAL_FALLBACK"
    $env:CORE_STATE_ROOT = $StateRoot
    $env:CORE_PUBLIC_ORIGIN = $origin
    $env:CORE_BIND_HOST = "127.0.0.1"
    $env:CORE_SPA_DIST_DIR = $SpaDistDir
    $env:CORE_RELEASE_CANDIDATE_ID = "local-fallback"
    $env:CORE_BUILD_MANIFEST_ID = "local-fallback"
    $env:CORE_OFFLINE_STARTUP = "true"
    $env:CORE_WEB_WORKER_COUNT = "1"
    $env:CORE_SQLITE_WRITER_COUNT = "1"
    $env:CORE_COMPUTE_SUBPROCESS_COUNT = "1"
    $env:CORE_GEMINI_ENABLED = "false"
    $env:CORE_API_PROXY_PREFIX = "/api"
    $env:CORE_E2E_BASE_URL = $origin
    $env:UV_CACHE_DIR = (Join-Path $Root ".uv-cache")
}

function Invoke-LocalFallbackPythonJson {
    param(
        [Parameter(Mandatory = $true)][string]$PythonPath,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    $raw = @(& $PythonPath @Arguments 2>$null)
    $exitCode = $LASTEXITCODE
    $text = ($raw -join "`n").Trim()
    $payload = $null
    if (-not [string]::IsNullOrWhiteSpace($text)) {
        try {
            $payload = $text | ConvertFrom-Json
        } catch {
            throw "The local fallback runtime check returned an invalid status."
        }
    }
    if ($exitCode -ne 0) {
        if ($null -ne $payload -and $payload.code -and $payload.recovery_action) {
            throw ("Local fallback check failed: {0}. Recovery: {1}." -f $payload.code, $payload.recovery_action)
        }
        throw "The local fallback runtime check failed."
    }
    if ($null -eq $payload) {
        throw "The local fallback runtime check returned no status."
    }
    return $payload
}

function Open-LocalFallbackLifecycleLock {
    param([Parameter(Mandatory = $true)][string]$StateRoot)

    $runtimeRoot = Join-Path $StateRoot "runtime"
    if (-not (Test-Path -LiteralPath $runtimeRoot -PathType Container)) {
        throw "Local fallback lifecycle state is unavailable; run setup.ps1 while online."
    }
    $lockPath = Join-Path $runtimeRoot "local-fallback.lock"
    try {
        $stream = [System.IO.File]::Open(
            $lockPath,
            [System.IO.FileMode]::OpenOrCreate,
            [System.IO.FileAccess]::ReadWrite,
            [System.IO.FileShare]::None
        )
    } catch {
        throw "Another local fallback lifecycle is already running."
    }
    try {
        $stream.SetLength(0)
        $bytes = [System.Text.Encoding]::UTF8.GetBytes("active")
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush($true)
    } catch {
        $stream.Dispose()
        throw "Local fallback lifecycle state is unavailable; run setup.ps1 again."
    }
    return $stream
}

function Close-LocalFallbackLifecycleLock {
    param([AllowNull()][System.IO.FileStream]$LockStream)

    if ($null -ne $LockStream) {
        $LockStream.Dispose()
    }
}

function Get-LocalFallbackProcessMarkerPath {
    param([Parameter(Mandatory = $true)][string]$StateRoot)

    return (Join-Path (Join-Path $StateRoot "runtime") "local-fallback-process.json")
}

function Assert-LocalFallbackNotRunning {
    param([Parameter(Mandatory = $true)][string]$StateRoot)

    $markerPath = Get-LocalFallbackProcessMarkerPath -StateRoot $StateRoot
    if (-not (Test-Path -LiteralPath $markerPath -PathType Leaf)) {
        return
    }
    try {
        $marker = (Get-Content -LiteralPath $markerPath -Raw) | ConvertFrom-Json
        $processId = [int]$marker.process_id
        $expectedStart = [string]$marker.process_start_time_utc
    } catch {
        throw "Local fallback lifecycle state is invalid; inspect the prepared runtime and retry."
    }
    try {
        $process = Get-Process -Id $processId -ErrorAction Stop
        $observedStart = $process.StartTime.ToUniversalTime().ToString("o")
        if ($process.ProcessName -like "python*" -and $observedStart -eq $expectedStart) {
            throw "Another local fallback lifecycle is already running."
        }
    } catch [System.Management.Automation.ItemNotFoundException] {
        Remove-Item -LiteralPath $markerPath -Force
        return
    } catch [System.ArgumentException] {
        Remove-Item -LiteralPath $markerPath -Force
        return
    }
    Remove-Item -LiteralPath $markerPath -Force
}

function Write-LocalFallbackProcessMarker {
    param(
        [Parameter(Mandatory = $true)][string]$StateRoot,
        [Parameter(Mandatory = $true)][System.Diagnostics.Process]$Process
    )

    $markerPath = Get-LocalFallbackProcessMarkerPath -StateRoot $StateRoot
    $temporaryPath = "{0}.{1}.tmp" -f $markerPath, ([guid]::NewGuid().ToString("N"))
    $payload = @{
        schema_version = "local-fallback-process.v1"
        process_id = $Process.Id
        process_start_time_utc = $Process.StartTime.ToUniversalTime().ToString("o")
        profile = "LOCAL_FALLBACK"
    } | ConvertTo-Json -Compress
    try {
        [System.IO.File]::WriteAllText($temporaryPath, $payload + [Environment]::NewLine, [Text.Encoding]::UTF8)
        Move-Item -LiteralPath $temporaryPath -Destination $markerPath -Force
    } finally {
        if (Test-Path -LiteralPath $temporaryPath -PathType Leaf) {
            Remove-Item -LiteralPath $temporaryPath -Force
        }
    }
}

function Remove-LocalFallbackProcessMarker {
    param([Parameter(Mandatory = $true)][string]$StateRoot)

    $markerPath = Get-LocalFallbackProcessMarkerPath -StateRoot $StateRoot
    if (Test-Path -LiteralPath $markerPath -PathType Leaf) {
        Remove-Item -LiteralPath $markerPath -Force
    }
}

function Get-LocalFallbackProcessFromMarker {
    param([Parameter(Mandatory = $true)][string]$StateRoot)

    $markerPath = Get-LocalFallbackProcessMarkerPath -StateRoot $StateRoot
    if (-not (Test-Path -LiteralPath $markerPath -PathType Leaf)) {
        return $null
    }
    try {
        $marker = (Get-Content -LiteralPath $markerPath -Raw) | ConvertFrom-Json
        $processId = [int]$marker.process_id
        $expectedStart = [string]$marker.process_start_time_utc
    } catch {
        throw "Local fallback lifecycle state is invalid; inspect the prepared runtime and retry."
    }
    try {
        $process = Get-Process -Id $processId -ErrorAction Stop
        $observedStart = $process.StartTime.ToUniversalTime().ToString("o")
        if ($process.ProcessName -notlike "python*" -or $observedStart -ne $expectedStart) {
            throw "The local fallback process marker does not identify the prepared server."
        }
        return $process
    } catch [System.Management.Automation.ItemNotFoundException] {
        Remove-LocalFallbackProcessMarker -StateRoot $StateRoot
        return $null
    } catch [System.ArgumentException] {
        Remove-LocalFallbackProcessMarker -StateRoot $StateRoot
        return $null
    }
}

function Request-LocalFallbackStop {
    try {
        $response = Invoke-WebRequest `
            -UseBasicParsing `
            -TimeoutSec 35 `
            -Method Post `
            -ContentType "application/json" `
            -Body "{}" `
            -Uri "http://127.0.0.1:8000/api/lifecycle/stop"
        $payload = $response.Content | ConvertFrom-Json
        if ($null -eq $payload -or $payload.schema_version -ne "lifecycle-stop.v1") {
            throw "The local fallback stop response was not typed."
        }
        return $payload
    } catch {
        throw "The local fallback could not confirm a safe stop; the process was left running."
    }
}

function Start-LocalFallbackServer {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$PythonPath
    )

    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $PythonPath
    $startInfo.Arguments = "-m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --workers 1"
    $startInfo.WorkingDirectory = $Root
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo
    if (-not $process.Start()) {
        $process.Dispose()
        throw "The local fallback server could not start."
    }
    return [pscustomobject]@{
        Process = $process
        StandardOutput = $process.StandardOutput.ReadToEndAsync()
        StandardError = $process.StandardError.ReadToEndAsync()
    }
}

function Stop-LocalFallbackServer {
    param(
        [AllowNull()][pscustomobject]$Server,
        [switch]$Graceful,
        [string]$StateRoot = ""
    )

    if ($null -eq $Server) {
        return
    }
    $process = $Server.Process
    try {
        if (-not $process.HasExited) {
            if ($Graceful) {
                if ([string]::IsNullOrWhiteSpace($StateRoot)) {
                    throw "The local fallback state root is required for a safe stop."
                }
                $stopResult = Request-LocalFallbackStop
                if ($stopResult.outcome -eq "STOP_FAILED") {
                    throw "The local fallback reported that safe stop could not be completed."
                }
            }
        }
        if (-not $process.HasExited) {
            $process.Kill()
            $process.WaitForExit()
        }
        $null = $Server.StandardOutput.GetAwaiter().GetResult()
        $null = $Server.StandardError.GetAwaiter().GetResult()
    } catch {
        if ($Graceful) {
            throw
        }
        # Cleanup is best effort after the server has stopped or failed.
    } finally {
        $process.Dispose()
    }
}

function Get-LocalFallbackProbe {
    param([Parameter(Mandatory = $true)][string]$Path)

    try {
        $response = Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 -Uri ("http://127.0.0.1:8000{0}" -f $Path)
        return [pscustomobject]@{
            StatusCode = [int]$response.StatusCode
            Body = ($response.Content | ConvertFrom-Json)
        }
    } catch {
        return $null
    }
}

function Wait-LocalFallbackReady {
    param(
        [Parameter(Mandatory = $true)][System.Diagnostics.Process]$Process,
        [int]$TimeoutSeconds = 60
    )

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        if ($Process.HasExited) {
            throw "The local fallback server stopped before Core readiness."
        }
        $live = Get-LocalFallbackProbe -Path "/api/health/live"
        $ready = Get-LocalFallbackProbe -Path "/api/health/ready"
        $health = Get-LocalFallbackProbe -Path "/api/health"
        if (
            $null -ne $live -and $live.StatusCode -eq 200 -and
            $live.Body.state -eq "live" -and $live.Body.code -eq "CORE_LIVE" -and
            $null -ne $ready -and $ready.StatusCode -eq 200 -and
            $ready.Body.state -in @("ready", "degraded") -and
            $ready.Body.code -in @("CORE_READY", "CORE_READY_GEMINI_DEGRADED") -and
            $null -ne $health -and $health.StatusCode -eq 200 -and
            $health.Body.liveness.state -eq "live" -and
            $health.Body.readiness.state -in @("ready", "degraded") -and
            $health.Body.code -in @("CORE_READY", "CORE_READY_GEMINI_DEGRADED")
        ) {
            return $health.Body
        }
        Start-Sleep -Milliseconds 250
    }
    throw "Core readiness was not established before the startup timeout."
}

function Assert-LocalFallbackSpa {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 -Uri "http://127.0.0.1:8000/"
        if ([int]$response.StatusCode -ne 200 -or [string]::IsNullOrWhiteSpace($response.Content)) {
            throw "empty response"
        }
    } catch {
        throw "The packaged SPA did not load from the local Core origin."
    }
}
