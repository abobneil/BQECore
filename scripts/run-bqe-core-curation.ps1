param(
    [string]$PythonPath = 'python',
    [string]$RepoRoot,
    [string]$ScriptPath,
    [string]$SourceDir,
    [string]$ExportsRoot,
    [string]$OutputDir,
    [string[]]$Tables = @(),
    [int]$RowsPerPart = 0,
    [int]$MaxRowsPerTable = 0,
    [switch]$ZipOutput,
    [string[]]$AdditionalArguments = @()
)

$ErrorActionPreference = 'Stop'

if (-not $RepoRoot) {
    $RepoRoot = Split-Path -Parent $PSScriptRoot
}

if (-not $ScriptPath) {
    $ScriptPath = Join-Path $RepoRoot 'scripts\curate_bqe_core_powerbi.py'
}

if (-not (Test-Path -LiteralPath $ScriptPath)) {
    throw "Curation script not found: $ScriptPath"
}

$arguments = @($ScriptPath)

if ($SourceDir) {
    $arguments += @('--source-dir', $SourceDir)
}

if ($ExportsRoot) {
    $arguments += @('--exports-root', $ExportsRoot)
}

if ($OutputDir) {
    $arguments += @('--output-dir', $OutputDir)
}

if ($RowsPerPart -gt 0) {
    $arguments += @('--rows-per-part', $RowsPerPart.ToString())
}

if ($MaxRowsPerTable -gt 0) {
    $arguments += @('--max-rows-per-table', $MaxRowsPerTable.ToString())
}

if ($Tables.Count -gt 0) {
    $arguments += '--tables'
    foreach ($table in $Tables) {
        if ($table) {
            $arguments += $table
        }
    }
}

if ($ZipOutput) {
    $arguments += '--zip-output'
}

if ($AdditionalArguments) {
    $arguments += $AdditionalArguments
}

Write-Host "Running BQE Core curation..."
Write-Host "$PythonPath $($arguments -join ' ')"

& $PythonPath @arguments
$exitCode = $LASTEXITCODE

if ($exitCode -ne 0) {
    throw "Curation failed with exit code $exitCode"
}
