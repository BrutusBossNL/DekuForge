param([Parameter(Mandatory=$true)][string]$Payload, [Parameter(Mandatory=$true)][string]$Root,
      [switch]$NoLaunch, [switch]$SkipTools, [switch]$NoShortcut)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
Add-Type -AssemblyName System.IO.Compression.FileSystem
$installRoot = [IO.Path]::GetFullPath($Root).TrimEnd('\')
if ($installRoot -eq [IO.Path]::GetPathRoot($installRoot).TrimEnd('\')) { throw 'Choose an application folder, not a drive root' }
$staging = Join-Path ([IO.Path]::GetDirectoryName($Payload)) 'application'
$archive = [IO.Compression.ZipFile]::OpenRead($Payload)
try {
    $size = 0L
    $seen = New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
    foreach ($entry in $archive.Entries) {
        $name = $entry.FullName
        $target = [IO.Path]::GetFullPath((Join-Path $staging $name))
        $size += $entry.Length
        if ($name.Contains('\') -or $name.Contains(':') -or -not $target.StartsWith($staging+'\',[StringComparison]::OrdinalIgnoreCase) -or -not $seen.Add($target) -or $size -gt 256MB -or (($entry.ExternalAttributes -shr 16) -band 61440) -eq 40960) { throw 'Unsafe installer payload' }
    }
} finally { $archive.Dispose() }
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
