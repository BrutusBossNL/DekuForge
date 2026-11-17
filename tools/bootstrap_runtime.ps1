param([Parameter(Mandatory=$true)][string]$Root)
$ErrorActionPreference = 'Stop'
function File-Sha256([string]$Path) {
    $algorithm=[Security.Cryptography.SHA256]::Create()
    $stream=[IO.File]::OpenRead($Path)
    try { return [BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-','').ToLowerInvariant() }
    finally { $stream.Dispose();$algorithm.Dispose() }
}
$ProgressPreference = 'SilentlyContinue'
$projectRoot = [IO.Path]::GetFullPath($Root).TrimEnd('\')
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot 'run_launcher.py'))) { throw 'Invalid DekuForge directory' }
function Assert-LocalPath([string]$Path) {
    $resolved = [IO.Path]::GetFullPath($Path)
    if (-not $resolved.StartsWith($projectRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Runtime path outside DekuForge' }
    $current = $resolved
    while ($current -and $current.Length -ge $projectRoot.Length) {
        if (Test-Path -LiteralPath $current) {
            if ((Get-Item -LiteralPath $current -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Linked runtime path refused' }
        }
        $current = [IO.Path]::GetDirectoryName($current)
    }
    return $resolved
}
$localFolder = Assert-LocalPath (Join-Path $projectRoot 'local')
[IO.Directory]::CreateDirectory($localFolder) | Out-Null
$logPath = Join-Path $localFolder 'runtime-bootstrap.log'
try {
    $components = Get-Content -Raw -LiteralPath (Join-Path $projectRoot 'dekuforge\components.json') | ConvertFrom-Json
    $pin = $components.python
    $expected = $pin.sha256
    if ($pin.id -notmatch '^[a-zA-Z0-9.-]+$' -or $expected -notmatch '^[0-9a-f]{64}$') { throw 'Invalid runtime identity' }
    $runtime = Assert-LocalPath (Join-Path $projectRoot ('python\' + $pin.id))
    $marker = Join-Path $runtime '.dekuforge-runtime.json'
    if (Test-Path -LiteralPath $runtime) {
        if ((Test-Path -LiteralPath $marker) -and ((Get-Content -Raw -LiteralPath $marker | ConvertFrom-Json).sha256 -eq $expected) -and (Test-Path -LiteralPath (Join-Path $runtime 'pythonw.exe'))) {
            [IO.File]::WriteAllText((Join-Path $localFolder 'python-path.txt'), (Join-Path $runtime 'python.exe') + "`n", (New-Object Text.UTF8Encoding($false)))
            exit 0
        }
        throw 'The Python directory already exists without the matching runtime marker'
    }
    $cache = Assert-LocalPath (Join-Path $localFolder 'build-tools')
    [IO.Directory]::CreateDirectory($cache) | Out-Null
    $archive = Join-Path $cache ('python-runtime-' + $pin.version + '.zip')
    if (-not ((Test-Path -LiteralPath $archive) -and ((File-Sha256 $archive) -eq $expected))) {
        $partial = Assert-LocalPath ($archive + '.part')
        Invoke-WebRequest -UseBasicParsing -Uri $pin.url -OutFile $partial
        if ((Get-Item -LiteralPath $partial).Length -ne $pin.size -or (File-Sha256 $partial) -ne $expected) { throw 'Runtime download checksum mismatch' }
        Move-Item -LiteralPath $partial -Destination $archive -Force
    }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $staging = Assert-LocalPath (Join-Path $localFolder ('python-stage-' + [Guid]::NewGuid().ToString('N')))
    [IO.Directory]::CreateDirectory($staging) | Out-Null
    $zip = [IO.Compression.ZipFile]::OpenRead($archive)
    try {
        $expanded = 0L
        $seen = New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
        if ($zip.Entries.Count -gt 20000) { throw 'Too many runtime archive members' }
        foreach ($entry in $zip.Entries) {
            $name = $entry.FullName.Replace('/', '\')
            $target = [IO.Path]::GetFullPath((Join-Path $staging $name))
            if (-not $target.StartsWith($staging + '\', [StringComparison]::OrdinalIgnoreCase) -or -not $seen.Add($target)) { throw 'Unsafe runtime archive member' }
            $expanded += $entry.Length
            if ($expanded -gt 512MB -or (($entry.ExternalAttributes -shr 16) -band 61440) -eq 40960) { throw 'Unsafe runtime archive type or size' }
        }
    } finally { $zip.Dispose() }
    [IO.Compression.ZipFile]::ExtractToDirectory($archive, $staging)
    [IO.File]::WriteAllText((Join-Path $staging 'python314._pth'), "python314.zip`n.`nLib/site-packages`n../../pydeps`n", [Text.Encoding]::ASCII)
    $identity = @{version=$pin.version;sha256=$expected;kind='CPython and launcher dependencies';game_files=$false} | ConvertTo-Json
    [IO.File]::WriteAllText((Join-Path $staging '.dekuforge-runtime.json'), $identity, [Text.Encoding]::UTF8)
    $checkedSource = Assert-LocalPath $staging
    $checkedTarget = Assert-LocalPath $runtime
    [IO.Directory]::CreateDirectory((Split-Path -Parent $checkedTarget)) | Out-Null
    Move-Item -LiteralPath $checkedSource -Destination $checkedTarget
    [IO.File]::WriteAllText((Join-Path $localFolder 'python-path.txt'), (Join-Path $runtime 'python.exe') + "`n", (New-Object Text.UTF8Encoding($false)))
    [IO.File]::WriteAllText($logPath, 'DekuForge runtime prepared and verified.', [Text.Encoding]::UTF8)
} catch {
    [IO.File]::WriteAllText($logPath, $_.ToString(), [Text.Encoding]::UTF8)
    exit 1
}
