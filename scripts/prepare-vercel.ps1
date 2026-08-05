param(
    [string]$RailwayPublicOrigin = $env:CORE_RAILWAY_PUBLIC_ORIGIN
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($RailwayPublicOrigin)) {
    throw "CORE_RAILWAY_PUBLIC_ORIGIN must be an HTTPS Railway service origin."
}

try {
    $origin = [Uri]$RailwayPublicOrigin.TrimEnd('/')
} catch {
    throw "CORE_RAILWAY_PUBLIC_ORIGIN must be a valid HTTPS origin."
}

if (
    $origin.Scheme -ne "https" -or
    [string]::IsNullOrWhiteSpace($origin.Host) -or
    $origin.AbsolutePath -ne "/" -or
    $origin.Query -ne "" -or
    $origin.Fragment -ne ""
) {
    throw "CORE_RAILWAY_PUBLIC_ORIGIN must be an HTTPS origin without a path, query, or fragment."
}

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$templatePath = Join-Path $root "vercel.json.template"
$configPath = Join-Path $root "vercel.json"
$template = Get-Content -LiteralPath $templatePath -Raw
$config = $template.Replace("__RAILWAY_PUBLIC_ORIGIN__", $origin.GetLeftPart([UriPartial]::Authority))
[System.IO.File]::WriteAllText(
    $configPath,
    $config,
    [System.Text.UTF8Encoding]::new($false)
)

Write-Output "Prepared vercel.json for the supplied Railway origin."
