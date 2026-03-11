param(
    [string]$PythonPath = 'python',
    [string]$RepoRoot,
    [string]$ExporterPath,
    [string]$EndpointFile,
    [string]$OutputRoot,
    [string]$TokenCache,
    [string]$ClientId = $env:BQE_CORE_CLIENT_ID,
    [string]$ClientSecret = $env:BQE_CORE_CLIENT_SECRET,
    [string]$RedirectUri = $env:BQE_CORE_REDIRECT_URI,
    [string]$AccessToken = $env:BQE_CORE_ACCESS_TOKEN,
    [string]$ApiBaseUrl = $env:BQE_CORE_API_BASE_URL,
    [string]$Scope = $env:BQE_CORE_SCOPE,
    [int]$PageSize = 1000,
    [int]$RequestTimeout = 120,
    [switch]$Incremental,
    [string]$IncrementalStateFile = $env:BQE_CORE_INCREMENTAL_STATE_FILE,
    [string]$IncrementalStart,
    [int]$IncrementalOverlapSeconds = 300,
    [string[]]$IncrementalField = @(),
    [switch]$NoIncrementalDeletes,
    [switch]$DownloadDocumentFiles,
    [switch]$FailFast,
    [string[]]$AdditionalArguments = @()
)

$ErrorActionPreference = 'Stop'

function Get-DefaultRepoRoot {
    return (Split-Path -Parent $PSScriptRoot)
}

function Get-DefaultTokenCache {
    return Join-Path $HOME '.bqe_core_export_tokens.json'
}

function Test-HasAuthMaterial {
    param(
        [string]$AccessToken,
        [string]$TokenCachePath
    )

    if ($AccessToken) {
        return $true
    }

    return (Test-Path -LiteralPath $TokenCachePath)
}

if (-not $RepoRoot) {
    $RepoRoot = Get-DefaultRepoRoot
}

if (-not $ExporterPath) {
    $ExporterPath = Join-Path $RepoRoot 'scripts\export_bqe_core.py'
}

if (-not $EndpointFile) {
    $EndpointFile = Join-Path $RepoRoot 'scripts\bqe-core-endpoints.txt'
}

if (-not $OutputRoot) {
    $OutputRoot = Join-Path $RepoRoot 'exports'
}

if (-not $TokenCache) {
    if ($env:BQE_CORE_TOKEN_CACHE) {
        $TokenCache = $env:BQE_CORE_TOKEN_CACHE
    }
    else {
        $TokenCache = Get-DefaultTokenCache
    }
}

if (-not (Test-Path -LiteralPath $ExporterPath)) {
    throw "Exporter script not found: $ExporterPath"
}

if (-not (Test-Path -LiteralPath $EndpointFile)) {
    throw "Endpoint file not found: $EndpointFile"
}

if (-not (Test-HasAuthMaterial -AccessToken $AccessToken -TokenCachePath $TokenCache)) {
    throw (
        "No non-interactive auth material found. Provide BQE_CORE_ACCESS_TOKEN or seed the token cache first by running " +
        "`"python scripts/export_bqe_core.py --client-id <id> --client-secret <secret> --redirect-uri <uri>`" once interactively."
    )
}

$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$outputDir = Join-Path $OutputRoot ("bqe-core-" + $timestamp)
$logDir = Join-Path $OutputRoot 'logs'
$logPath = Join-Path $logDir ("bqe-core-" + $timestamp + '.log')

New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$arguments = @(
    $ExporterPath,
    '--output-dir', $outputDir,
    '--endpoints-file', $EndpointFile,
    '--page-size', $PageSize.ToString(),
    '--request-timeout', $RequestTimeout.ToString(),
    '--token-cache', $TokenCache,
    '--no-browser'
)

if ($AccessToken) {
    $arguments += @('--access-token', $AccessToken)
}

if ($ClientId) {
    $arguments += @('--client-id', $ClientId)
}

if ($ClientSecret) {
    $arguments += @('--client-secret', $ClientSecret)
}

if ($RedirectUri) {
    $arguments += @('--redirect-uri', $RedirectUri)
}

if ($ApiBaseUrl) {
    $arguments += @('--api-base-url', $ApiBaseUrl)
}

if ($Scope) {
    $arguments += @('--scope', $Scope)
}

if ($Incremental) {
    $arguments += '--incremental'
}

if ($IncrementalStateFile) {
    $arguments += @('--incremental-state-file', $IncrementalStateFile)
}

if ($IncrementalStart) {
    $arguments += @('--incremental-start', $IncrementalStart)
}

if ($IncrementalOverlapSeconds -ge 0) {
    $arguments += @('--incremental-overlap-seconds', $IncrementalOverlapSeconds.ToString())
}

foreach ($fieldOverride in $IncrementalField) {
    if ($fieldOverride) {
        $arguments += @('--incremental-field', $fieldOverride)
    }
}

if ($NoIncrementalDeletes) {
    $arguments += '--no-incremental-deletes'
}

if ($DownloadDocumentFiles) {
    $arguments += '--download-document-files'
}

if ($FailFast) {
    $arguments += '--fail-fast'
}

if ($AdditionalArguments.Count -gt 0) {
    $arguments += $AdditionalArguments
}

Write-Host "Export starting..."
Write-Host "Repo root: $RepoRoot"
Write-Host "Output directory: $outputDir"
Write-Host "Log file: $logPath"

Push-Location $RepoRoot
try {
    & $PythonPath @arguments 2>&1 | Tee-Object -FilePath $logPath
    $exitCode = $LASTEXITCODE
}
finally {
    Pop-Location
}

if ($null -eq $exitCode) {
    $exitCode = 0
}

if ($exitCode -ne 0) {
    Write-Error "BQE Core export failed. See $logPath"
}

Write-Host "BQE Core export completed."
Write-Host "Output directory: $outputDir"
Write-Host "Log file: $logPath"
exit $exitCode
