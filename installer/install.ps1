param([Parameter(Mandatory=$true)][string]$Payload, [Parameter(Mandatory=$true)][string]$Root,
      [switch]$NoLaunch, [switch]$SkipTools, [switch]$NoShortcut)
$ErrorActionPreference = 'Stop'
function File-Sha256([string]$Path) {
    $algorithm=[Security.Cryptography.SHA256]::Create()
    $stream=[IO.File]::OpenRead($Path)
    try { return [BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-','').ToLowerInvariant() }
    finally { $stream.Dispose();$algorithm.Dispose() }
}
$ProgressPreference = 'SilentlyContinue'
Add-Type -AssemblyName System.IO.Compression.FileSystem
function Get-InstallerStaging([string]$PayloadPath) {
    # .NET expands existing Windows 8.3 names. Resolve the extraction root with
    # the same API as entry targets before comparing their containment.
    $canonicalPayload = [IO.Path]::GetFullPath($PayloadPath)
    $stagingRoot = [IO.Path]::GetFullPath((Join-Path ([IO.Path]::GetDirectoryName($canonicalPayload)) 'application'))
    $archive = [IO.Compression.ZipFile]::OpenRead($canonicalPayload)
    try {
        $size = 0L
        $seen = New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
        if ($archive.Entries.Count -gt 20000) { throw 'Unsafe installer payload: too many entries' }
        foreach ($entry in $archive.Entries) {
            $name = $entry.FullName
            if ($name.Contains('\') -or $name.Contains(':') -or [IO.Path]::IsPathRooted($name) -or ($name.Split('/') -contains '..')) {
                throw "Unsafe installer payload: invalid entry name '$name'"
            }
            $target = [IO.Path]::GetFullPath((Join-Path $stagingRoot $name))
            if (-not $target.StartsWith($stagingRoot+'\',[StringComparison]::OrdinalIgnoreCase)) {
                throw "Unsafe installer payload: entry '$name' escapes the extraction folder"
            }
            if (-not $seen.Add($target)) { throw "Unsafe installer payload: duplicate entry '$name'" }
            $size += $entry.Length
            if ($size -gt 256MB) { throw 'Unsafe installer payload: expanded size exceeds 256 MiB' }
            if ((($entry.ExternalAttributes -shr 16) -band 61440) -eq 40960) {
                throw "Unsafe installer payload: symbolic link '$name'"
            }
        }
    } finally { $archive.Dispose() }
    return $stagingRoot
}
$Payload = [IO.Path]::GetFullPath($Payload)
$installRoot = [IO.Path]::GetFullPath($Root).TrimEnd('\')
if ($installRoot -eq [IO.Path]::GetPathRoot($installRoot).TrimEnd('\')) { throw 'Choose an application folder, not a drive root' }
$staging = Get-InstallerStaging $Payload
[IO.Compression.ZipFile]::ExtractToDirectory($Payload,$staging)
$pins = Get-Content -Raw -LiteralPath (Join-Path $staging 'dekuforge\components.json') | ConvertFrom-Json
$runtime = Join-Path $installRoot ('python\'+$pins.python.id)
$pythonExe = Join-Path $runtime 'python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) {
    Write-Output 'Downloading and verifying the launcher runtime...'
    & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File (Join-Path $staging 'tools\bootstrap_runtime.ps1') -Root $staging
    if ($LASTEXITCODE -ne 0) { throw 'Runtime preparation failed' }
    $pythonExe = Join-Path $staging ('python\'+$pins.python.id+'\python.exe')
}
Write-Output 'Installing DekuForge application files...'
$installArgs = @((Join-Path $staging 'tools\install_package.py'),'--package',$Payload,'--root',$installRoot)
if ($SkipTools) { $installArgs += '--skip-tools' }
if ($NoShortcut) { $installArgs += '--no-shortcut' }
if ($NoLaunch) { $installArgs += '--no-launch' }
& $pythonExe @installArgs
if ($LASTEXITCODE -ne 0) { throw 'DekuForge installation failed; see setup log' }
Write-Output 'DekuForge installation completed.'
