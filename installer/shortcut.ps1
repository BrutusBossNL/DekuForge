param([Parameter(Mandatory=$true)][string]$Root)
$ErrorActionPreference='Stop'
$target=Join-Path ([IO.Path]::GetFullPath($Root)) 'DekuForge.exe'
if (-not (Test-Path -LiteralPath $target)) { throw 'Launcher is missing' }
$shell=New-Object -ComObject WScript.Shell
$link=$shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Programs')) 'DekuForge.lnk'))
$link.TargetPath=$target
$link.WorkingDirectory=[IO.Path]::GetDirectoryName($target)
$link.IconLocation=$target+',0'
$link.Save()
