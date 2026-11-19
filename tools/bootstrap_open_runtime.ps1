param([Parameter(Mandatory=$true)][string]$Root)
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$projectRoot=[IO.Path]::GetFullPath($Root).TrimEnd('\')
function Local-Path([string]$Path) {
    $resolved=[IO.Path]::GetFullPath($Path)
    if (-not $resolved.StartsWith($projectRoot+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Runtime path outside project' }
    $current=$resolved
    while ($current -and $current.Length -ge $projectRoot.Length) {
        if ((Test-Path -LiteralPath $current) -and ((Get-Item -LiteralPath $current -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Linked runtime path refused' }
        $current=[IO.Path]::GetDirectoryName($current)
    }
    return $resolved
}
function File-Sha256([string]$Path) {
    $algorithm=[Security.Cryptography.SHA256]::Create()
    $stream=[IO.File]::OpenRead($Path)
    try { return [BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-','').ToLowerInvariant() }
    finally { $stream.Dispose(); $algorithm.Dispose() }
}
function Fetch-Pinned($Pin,[string]$Name) {
    if ($Pin.sha256 -notmatch '^[0-9a-f]{64}$' -or $Pin.size -lt 1 -or $Pin.size -gt 100MB) { throw 'Invalid generic runtime pin' }
    $file=Local-Path (Join-Path $cache $Name)
    if (-not ((Test-Path -LiteralPath $file) -and (Get-Item -LiteralPath $file).Length -eq $Pin.size -and (File-Sha256 $file) -eq $Pin.sha256)) {
        $partial=Local-Path ($file+'.part')
        Invoke-WebRequest -UseBasicParsing -Uri $Pin.url -OutFile $partial
        if ((Get-Item -LiteralPath $partial).Length -ne $Pin.size -or (File-Sha256 $partial) -ne $Pin.sha256) { throw 'Generic runtime checksum mismatch' }
        Move-Item -LiteralPath $partial -Destination $file -Force
    }
    return $file
}
$localFolder=Local-Path (Join-Path $projectRoot 'local')
[IO.Directory]::CreateDirectory($localFolder) | Out-Null
$log=Join-Path $localFolder 'runtime-bootstrap.log'
try {
    $pin=(Get-Content -LiteralPath (Join-Path $projectRoot 'dekuforge/components.json') -Raw | ConvertFrom-Json).python
    if ($pin.id -notmatch '^[a-zA-Z0-9.-]+$' -or $pin.source -ne 'astral-python-build-standalone') { throw 'Unsupported independent runtime provider' }
    $runtime=Local-Path (Join-Path $projectRoot ('python/'+$pin.id))
    $marker=Join-Path $runtime '.dekuforge-runtime.json'
    if (Test-Path -LiteralPath $runtime) {
        $record=if (Test-Path -LiteralPath $marker) { Get-Content -LiteralPath $marker -Raw | ConvertFrom-Json } else { $null }
        if ($record.sha256 -ne $pin.sha256 -or $record.pillow_sha256 -ne $pin.pillow.sha256 -or -not (Test-Path -LiteralPath (Join-Path $runtime 'pythonw.exe'))) { throw 'Existing runtime is unowned or has another identity' }
    } else {
        $cache=Local-Path (Join-Path $localFolder 'build-tools')
        [IO.Directory]::CreateDirectory($cache) | Out-Null
        $archive=Fetch-Pinned $pin ('cpython-'+$pin.version+'-20261110.tar.gz')
        $wheel=Fetch-Pinned $pin.pillow 'pillow-12.0.0-cp314-win_amd64.whl'
        $staging=Local-Path (Join-Path $localFolder ('python-stage-'+[Guid]::NewGuid().ToString('N')))
        [IO.Directory]::CreateDirectory($staging) | Out-Null
        $tar=Join-Path ([Environment]::SystemDirectory) 'tar.exe'
        if (-not (Test-Path -LiteralPath $tar)) { throw 'Windows tar.exe is required for this independent runtime' }
        $names=@(& $tar -tf $archive)
        if ($LASTEXITCODE -ne 0 -or $names.Count -lt 1 -or $names.Count -gt 20000) { throw 'Invalid runtime archive index' }
        $seen=New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
        foreach ($name in $names) {
            if (-not $name.StartsWith('python/') -or $name -match '(^|/)\.\.(/|$)|[:\\]' -or -not $seen.Add($name.TrimEnd('/'))) { throw 'Unsafe runtime archive path' }
            $target=Local-Path (Join-Path $staging $name)
            if (-not $target.StartsWith($staging+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe runtime extraction path' }
        }
        $details=@(& $tar -tvf $archive)
        if ($LASTEXITCODE -ne 0 -or $details.Count -ne $names.Count) { throw 'Invalid runtime archive types' }
        $expanded=0L
        foreach ($line in $details) {
            if ($line -notmatch '^[d-]\S*\s+\d+\s+\S+\s+\S+\s+(\d+)\s') { throw 'Runtime archive links or special files refused' }
            $expanded += [long]$Matches[1]
            if ($expanded -gt 128MB) { throw 'Runtime expansion limit exceeded' }
        }
        & $tar -xf $archive -C $staging
        if ($LASTEXITCODE -ne 0) { throw 'Runtime extraction failed' }
        $python=Local-Path (Join-Path $staging 'python')
        $packages=Local-Path (Join-Path $python 'Lib/site-packages')
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $zip=[IO.Compression.ZipFile]::OpenRead($wheel)
        try {
            $expanded=0L
            $seen.Clear()
            foreach ($entry in $zip.Entries) {
                $target=Local-Path (Join-Path $packages $entry.FullName)
                if (-not $target.StartsWith($packages+'\',[StringComparison]::OrdinalIgnoreCase) -or -not $seen.Add($target) -or (($entry.ExternalAttributes -shr 16) -band 61440) -eq 40960) { throw 'Unsafe Pillow archive member' }
                $expanded += $entry.Length
                if ($expanded -gt 64MB) { throw 'Pillow expansion limit exceeded' }
            }
        } finally { $zip.Dispose() }
        [IO.Compression.ZipFile]::ExtractToDirectory($wheel,$packages)
        & (Join-Path $python 'python.exe') -I -c 'import tkinter,PIL,ssl; print(PIL.__version__)'
        if ($LASTEXITCODE -ne 0) { throw 'Independent Python/Tk/Pillow check failed' }
        $identity=@{version=$pin.version;sha256=$pin.sha256;pillow_sha256=$pin.pillow.sha256;provider=$pin.source;game_files=$false} | ConvertTo-Json
        [IO.File]::WriteAllText((Join-Path $python '.dekuforge-runtime.json'),$identity,(New-Object Text.UTF8Encoding($false)))
        [IO.Directory]::CreateDirectory((Split-Path -Parent $runtime)) | Out-Null
        Move-Item -LiteralPath $python -Destination $runtime
        Remove-Item -LiteralPath $staging
    }
    [IO.File]::WriteAllText((Join-Path $localFolder 'python-path.txt'),(Join-Path $runtime 'python.exe')+"`n",(New-Object Text.UTF8Encoding($false)))
    [IO.File]::WriteAllText($log,'Official standalone Python/Tk and pinned Pillow prepared; no NX2navi runtime used.',[Text.Encoding]::UTF8)
} catch {
    [IO.File]::WriteAllText($log,$_.ToString(),[Text.Encoding]::UTF8)
    exit 1
}
exit 0
