param(
    [switch]$StagedOnly
)

$ErrorActionPreference = 'Stop'

function Get-RepoRoot {
    $root = git rev-parse --show-toplevel 2>$null
    if (-not $root) {
        throw 'This script must run inside a git repository.'
    }

    return $root.Trim()
}

function Get-TargetFiles {
    param(
        [string]$RepoRoot,
        [switch]$StagedOnly
    )

    Push-Location $RepoRoot
    try {
        if ($StagedOnly) {
            $output = git diff --cached --name-only --diff-filter=ACMR
        }
        else {
            $output = git ls-files
        }
    }
    finally {
        Pop-Location
    }

    return @($output | Where-Object { $_ -and $_.Trim() })
}

function Has-SuspiciousDirectory {
    param(
        [string]$RelativePath,
        [string[]]$SuspiciousDirectories
    )

    $segments = $RelativePath -split '[\\/]'
    foreach ($segment in $segments) {
        if ($SuspiciousDirectories -contains $segment.ToLowerInvariant()) {
            return $true
        }
    }

    return $false
}

$repoRoot = Get-RepoRoot
$targetFiles = Get-TargetFiles -RepoRoot $repoRoot -StagedOnly:$StagedOnly

if (-not $targetFiles -or $targetFiles.Count -eq 0) {
    Write-Host 'No files to inspect.'
    exit 0
}

$blockedFileNames = @(
    '.env',
    '.env.local',
    '.env.development',
    '.env.production',
    'id_rsa',
    'id_dsa',
    'id_ecdsa',
    'id_ed25519',
    'secrets.json',
    'local.settings.json'
)

$blockedExtensions = @(
    '.pem',
    '.key',
    '.pfx',
    '.p12',
    '.jks',
    '.keystore',
    '.kdbx',
    '.ovpn',
    '.gpg',
    '.pgp',
    '.publishsettings',
    '.tfstate',
    '.tfvars'
)

$suspiciousDirectories = @('backup', 'backups', 'dump', 'dumps', 'export', 'exports')
$blockedDataExtensions = @('.bak', '.csv', '.parquet', '.sql', '.sqlite', '.db', '.tsv', '.xlsx', '.avro')

$violations = New-Object System.Collections.Generic.List[string]

foreach ($relativePath in $targetFiles) {
    $fullPath = Join-Path $repoRoot $relativePath
    if (-not (Test-Path -LiteralPath $fullPath)) {
        continue
    }

    $fileName = [System.IO.Path]::GetFileName($relativePath).ToLowerInvariant()
    $extension = [System.IO.Path]::GetExtension($relativePath).ToLowerInvariant()

    if ($blockedFileNames -contains $fileName) {
        $violations.Add("${relativePath}: blocked secret-bearing filename")
        continue
    }

    if ($blockedExtensions -contains $extension) {
        $violations.Add("${relativePath}: blocked secret-bearing file extension")
        continue
    }

    if ((Has-SuspiciousDirectory -RelativePath $relativePath -SuspiciousDirectories $suspiciousDirectories) -and ($blockedDataExtensions -contains $extension)) {
        $violations.Add("${relativePath}: likely export, dump, or backup content")
        continue
    }
}

if ($violations.Count -gt 0) {
    Write-Error ("Sensitive content policy failed:`n - " + ($violations -join "`n - "))
}

Write-Host ("Sensitive content policy passed for {0} file(s)." -f $targetFiles.Count)
