param([Parameter(Mandatory=$true)][string]$Root)
$ErrorActionPreference='Stop'
$target=Join-Path ([IO.Path]::GetFullPath($Root)) 'DekuForge.exe'
if (-not (Test-Path -LiteralPath $target)) { throw 'Launcher is missing' }
$shell=New-Object -ComObject WScript.Shell
$link=$shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Programs')) 'DekuForge Preview.lnk'))
$link.TargetPath=$target
$link.WorkingDirectory=[IO.Path]::GetDirectoryName($target)
$link.IconLocation=$target+',0'
$link.Save()
$rootPath=[IO.Path]::GetFullPath($Root).TrimEnd('\')
$components=Get-Content -Raw -LiteralPath (Join-Path $rootPath 'dekuforge\components.json') | ConvertFrom-Json
$registry='HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\DekuForgePreview'
New-Item -Path $registry -Force | Out-Null
New-ItemProperty -LiteralPath $registry -Name DisplayName -Value 'DekuForge' -PropertyType String -Force | Out-Null
New-ItemProperty -LiteralPath $registry -Name DisplayVersion -Value $components.launcher.version -PropertyType String -Force | Out-Null
New-ItemProperty -LiteralPath $registry -Name InstallLocation -Value $rootPath -PropertyType String -Force | Out-Null
New-ItemProperty -LiteralPath $registry -Name UninstallString -Value ('"'+(Join-Path $rootPath 'DekuForge-Uninstall.exe')+'"') -PropertyType String -Force | Out-Null
New-ItemProperty -LiteralPath $registry -Name DisplayIcon -Value $target -PropertyType String -Force | Out-Null
New-ItemProperty -LiteralPath $registry -Name Publisher -Value 'DekuForge contributors' -PropertyType String -Force | Out-Null
New-ItemProperty -LiteralPath $registry -Name NoModify -Value 1 -PropertyType DWord -Force | Out-Null
New-ItemProperty -LiteralPath $registry -Name NoRepair -Value 1 -PropertyType DWord -Force | Out-Null
