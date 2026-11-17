param([Parameter(Mandatory=$true)][string]$Root,[switch]$Silent,[switch]$Confirm,
      [switch]$RemoveSaves,[string]$Backup,[switch]$PlanOnly,[switch]$NoShellCleanup)
$ErrorActionPreference='Stop'
function File-Sha256([string]$Path) {
    $algorithm=[Security.Cryptography.SHA256]::Create()
    $stream=[IO.File]::OpenRead($Path)
    try { return [BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-','').ToLowerInvariant() }
    finally { $stream.Dispose();$algorithm.Dispose() }
}
trap {
    if (-not $Silent) { Add-Type -AssemblyName System.Windows.Forms;[Windows.Forms.MessageBox]::Show($_.Exception.Message,'DekuForge uninstall') | Out-Null }
    else { Write-Output $_.Exception.Message }
    exit 1
}
$installRoot=[IO.Path]::GetFullPath($Root).TrimEnd('\')
if ($installRoot -eq [IO.Path]::GetPathRoot($installRoot).TrimEnd('\') -or (Test-Path -LiteralPath (Join-Path $installRoot '.git'))) { throw 'Uninstall only a setup-owned installation, not a source checkout or drive root' }
$identityPath=Join-Path $installRoot 'local\installation.json'
if (-not (Test-Path -LiteralPath $identityPath) -or (Get-Content -Raw -LiteralPath $identityPath | ConvertFrom-Json).kind -ne 'DekuForge') { throw 'This directory is not a setup-owned DekuForge installation' }
$inventory=Get-Content -Raw -LiteralPath (Join-Path $installRoot 'local\installed-package.json') | ConvertFrom-Json
$protected=New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
$archives=@('.nup','.nsp','.nsz','.xci','.xcz','.rom','.z64','.n64','.v64','.nca','.nso','.ncz','.iso','.keys')
function Protect-Input([string]$Value) {
    if ($Value) { [void]$protected.Add([IO.Path]::GetFullPath($Value)) }
}
$settingsPath=Join-Path $installRoot 'local\settings.json'
if (Test-Path -LiteralPath $settingsPath) {
    $settings=Get-Content -Raw -LiteralPath $settingsPath | ConvertFrom-Json
    Protect-Input $settings.nup
}
$targets=New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
$profiles=New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
foreach ($name in @('build','local','python','pydeps','__pycache__','dekuforge\__pycache__','tools\__pycache__')) {
    $path=[IO.Path]::GetFullPath((Join-Path $installRoot $name))
    if (Test-Path -LiteralPath $path) { [void]$targets.Add($path) }
}
$libraryPath=Join-Path $installRoot 'local\builds.json'
if (Test-Path -LiteralPath $libraryPath) {
    $buildEntries=Get-Content -Raw -LiteralPath $libraryPath | ConvertFrom-Json
    foreach ($entry in $buildEntries) {
        Protect-Input $entry.dump
        if (-not $entry.owned) { continue }
        $folder=[IO.Path]::GetFullPath([IO.Path]::GetDirectoryName($entry.executable)).TrimEnd('\')
        if (-not (Test-Path -LiteralPath $folder)) { continue }
        if ($folder -eq $installRoot -or $installRoot.StartsWith($folder+'\',[StringComparison]::OrdinalIgnoreCase) -or $folder -eq [IO.Path]::GetPathRoot($folder).TrimEnd('\')) { throw 'Unsafe managed build root' }
        $marker=Join-Path $folder '.dekuforge-build.json'
        if (-not (Test-Path -LiteralPath $marker)) { throw "Managed build ownership marker is missing: $folder" }
        $record=Get-Content -Raw -LiteralPath $marker | ConvertFrom-Json
        if ($record.id -ne $entry.id -or $record.executable -ne [IO.Path]::GetFileName($entry.executable)) { throw 'Managed build ownership does not match' }
        [void]$targets.Add($folder)
        $profile=Join-Path $folder 'profile'
        if (Test-Path -LiteralPath $profile) { [void]$profiles.Add($profile) }
    }
}
foreach ($path in @((Join-Path $installRoot 'local\retained-saves'),(Join-Path $installRoot 'local\preserved-saves-before-cleanup'),(Join-Path $installRoot 'profile'))) {
    if (Test-Path -LiteralPath $path) { [void]$profiles.Add($path) }
}
$allFiles=New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
$directories=New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
foreach ($target in $targets) {
    $item=Get-Item -LiteralPath $target -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Linked managed folders are never followed by uninstall' }
    [void]$directories.Add($target)
    foreach ($item in Get-ChildItem -LiteralPath $target -Force -Recurse) {
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Linked managed content is never followed by uninstall' }
        if ($item.PSIsContainer) {
            [void]$directories.Add($item.FullName)
            if ($item.Name -eq 'profile' -and ((Test-Path -LiteralPath (Join-Path $item.Parent.FullName '.dekuforge-stable-build')) -or (Test-Path -LiteralPath (Join-Path $item.Parent.FullName '.dekuforge-owned')))) { [void]$profiles.Add($item.FullName) }
        } else { [void]$allFiles.Add($item.FullName) }
    }
}
foreach ($property in $inventory.sha256.PSObject.Properties) {
    $name=$property.Name.Replace('/','\')
    $path=[IO.Path]::GetFullPath((Join-Path $installRoot $name))
    if (-not $path.StartsWith($installRoot+'\',[StringComparison]::OrdinalIgnoreCase) -or $name -match '(^|\\)\.\.($|\\)') { throw 'Unsafe application inventory path' }
    if (Test-Path -LiteralPath $path) {
        if ((Get-Item -LiteralPath $path -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Linked application file refused' }
        [void]$allFiles.Add($path)
        $parent=[IO.Path]::GetDirectoryName($path)
        while ($parent.StartsWith($installRoot+'\',[StringComparison]::OrdinalIgnoreCase)) { [void]$directories.Add($parent);$parent=[IO.Path]::GetDirectoryName($parent) }
    }
}
foreach ($path in @($allFiles)) {
    if ($archives -contains [IO.Path]::GetExtension($path).ToLowerInvariant()) { Protect-Input $path }
}
$deleteFiles=@($allFiles | Where-Object { -not $protected.Contains($_) } | Sort-Object @{Expression={
    if ([IO.Path]::GetFileName($_) -in @('installation.json','installed-package.json','builds.json','settings.json','.dekuforge-build.json','.dekuforge-owned','.dekuforge-stable-build','DekuForge-Uninstall.exe')) { 1 } else { 0 }
}})
$plan=@{root=$installRoot;managed_directories=@($targets);profiles=@($profiles);protected_inputs=@($protected);delete_file_count=$deleteFiles.Count}
if ($PlanOnly) { $plan | ConvertTo-Json -Depth 8;exit 0 }
function Invoke-Uninstall([bool]$Keep,[string]$Destination) {
    if (-not $Confirm -and $Silent) { throw 'Silent uninstall requires explicit -Confirm' }
    $backupRoot=$null
    if ($Keep) {
        if (-not $Destination) { throw 'Choose a save backup location' }
        $backupRoot=[IO.Path]::GetFullPath($Destination).TrimEnd('\')
        foreach ($target in @($targets)+@($installRoot)) {
            if ($backupRoot -eq $target -or $backupRoot.StartsWith($target+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Save backup must be outside every removed directory' }
        }
        if (Test-Path -LiteralPath $backupRoot) { throw 'Choose a new save backup folder' }
    }
    # Refuse running games/launchers/build tools; never stop a user's process to uninstall.
    foreach ($process in [Diagnostics.Process]::GetProcesses()) {
        try { $program=$process.MainModule.FileName } catch { continue }
        foreach ($target in @($targets)+@($installRoot)) {
            if ($program -and $program.StartsWith($target+'\',[StringComparison]::OrdinalIgnoreCase)) { throw "Close the running DekuForge game, launcher or build tools before uninstalling: $($process.ProcessName)" }
        }
    }
    if ($Keep) {
        [IO.Directory]::CreateDirectory($backupRoot) | Out-Null
        $number=0
        foreach ($profile in $profiles) {
            $number++
            $destination=Join-Path $backupRoot ('profile-'+$number)
            [IO.Directory]::CreateDirectory($destination) | Out-Null
            foreach ($file in Get-ChildItem -LiteralPath $profile -File -Force -Recurse) {
                if ($protected.Contains($file.FullName)) { continue }
                $relative=$file.FullName.Substring($profile.Length).TrimStart('\')
                $copy=Join-Path $destination $relative
                [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($copy)) | Out-Null
                Copy-Item -LiteralPath $file.FullName -Destination $copy
                if ((File-Sha256 $file.FullName) -ne (File-Sha256 $copy)) { throw 'Save backup verification failed; nothing was removed' }
            }
        }
        $plan | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $backupRoot 'DekuForge-saves.json')
    }
    # Paths were enumerated only from setup-owned roots or matching build ownership markers.
    foreach ($path in $deleteFiles) {
        if ($protected.Contains($path)) { throw 'A game archive reached the deletion plan' }
        if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Force -ErrorAction Stop }
    }
    foreach ($path in @($directories | Sort-Object Length -Descending)) {
        if ((Test-Path -LiteralPath $path) -and -not (Get-ChildItem -LiteralPath $path -Force | Select-Object -First 1)) { [IO.Directory]::Delete($path,$false) }
    }
    if (-not $NoShellCleanup) {
        $shortcut=Join-Path ([Environment]::GetFolderPath('Programs')) 'DekuForge.lnk'
        if (Test-Path -LiteralPath $shortcut) {
            $shell=New-Object -ComObject WScript.Shell
            if ($shell.CreateShortcut($shortcut).TargetPath -eq (Join-Path $installRoot 'DekuForge.exe')) { Remove-Item -LiteralPath $shortcut -Force }
        }
        $registry='HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\DekuForge'
        if ((Test-Path $registry) -and (Get-ItemProperty $registry).InstallLocation -eq $installRoot) { Remove-Item -LiteralPath $registry -Recurse -Force }
    }
    if (-not (Get-ChildItem -LiteralPath $installRoot -Force | Select-Object -First 1)) { [IO.Directory]::Delete($installRoot,$false) }
    return $backupRoot
}
if ($Silent) {
    $saved=Invoke-Uninstall (-not $RemoveSaves) $Backup
    if ($saved) { @{success=$true;original_inputs_untouched=$true} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $saved 'DekuForge-uninstall-result.json') }
    Write-Output "DekuForge removed. Save backup: $saved. Original game archives were not modified.";exit 0
}
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[Windows.Forms.Application]::EnableVisualStyles()
$form=New-Object Windows.Forms.Form
$form.Text='Uninstall DekuForge';$form.Size=New-Object Drawing.Size(700,520);$form.StartPosition='CenterScreen'
try { $form.Icon=[Drawing.Icon]::ExtractAssociatedIcon((Join-Path $installRoot 'DekuForge-Uninstall.exe')) } catch {}
$form.BackColor=[Drawing.Color]::FromArgb(12,30,19);$form.ForeColor=[Drawing.Color]::FromArgb(231,242,225);$form.Font=New-Object Drawing.Font('Segoe UI',10)
$form.FormBorderStyle='FixedDialog';$form.MaximizeBox=$false
$label=New-Object Windows.Forms.Label;$label.SetBounds(24,20,640,55);$label.Text='Remove DekuForge, all builds managed by this installation and its downloaded tools. Your original game archives will never be deleted.';$form.Controls.Add($label)
$list=New-Object Windows.Forms.ListBox;$list.SetBounds(24,85,640,160);$list.BackColor=$form.BackColor;$list.ForeColor=$form.ForeColor
[void]$list.Items.Add($installRoot);foreach ($target in $targets) { [void]$list.Items.Add($target) };$form.Controls.Add($list)
$keep=New-Object Windows.Forms.CheckBox;$keep.SetBounds(24,260,600,30);$keep.Text='Keep my saves (verified backup outside the installation)';$keep.Checked=$true;$form.Controls.Add($keep)
$folder=New-Object Windows.Forms.TextBox;$folder.SetBounds(24,300,520,30);$folder.Text=Join-Path ([Environment]::GetFolderPath('MyDocuments')) ('DekuForge Saves\'+(Get-Date -Format 'yyyyMMdd-HHmmss'));$form.Controls.Add($folder)
$folder.BackColor=$form.BackColor;$folder.ForeColor=$form.ForeColor
$browse=New-Object Windows.Forms.Button;$browse.SetBounds(555,298,108,32);$browse.Text='Browse...';$form.Controls.Add($browse)
$browse.FlatStyle='Flat';$browse.BackColor=[Drawing.Color]::FromArgb(48,74,40)
$browse.Add_Click({$dialog=New-Object Windows.Forms.FolderBrowserDialog;if ($dialog.ShowDialog() -eq 'OK') { $folder.Text=Join-Path $dialog.SelectedPath ('DekuForge-Saves-'+(Get-Date -Format 'yyyyMMdd-HHmmss')) }})
$keep.Add_CheckedChanged({$folder.Enabled=$keep.Checked;$browse.Enabled=$keep.Checked})
$status=New-Object Windows.Forms.Label;$status.SetBounds(24,345,640,50);$status.Text='No game dump is moved, read or modified by uninstall. Only its configured path is used to protect it.';$form.Controls.Add($status)
$remove=New-Object Windows.Forms.Button;$remove.SetBounds(440,415,220,36);$remove.Text='Uninstall DekuForge';$form.Controls.Add($remove)
$remove.FlatStyle='Flat';$remove.BackColor=[Drawing.Color]::FromArgb(235,185,77);$remove.ForeColor=$form.BackColor
$remove.Add_Click({
    if ([Windows.Forms.MessageBox]::Show('Remove this DekuForge installation and its managed builds/tools?','DekuForge','YesNo','Warning') -ne 'Yes') { return }
    try { $remove.Enabled=$false;$status.Text='Checking save backups and removing owned files...';$form.Refresh();$saved=Invoke-Uninstall $keep.Checked $folder.Text;[Windows.Forms.MessageBox]::Show(('DekuForge removed. Your original game archives were not modified.'+$(if ($saved) {"`nSaves: $saved"} else {''})),'DekuForge');$form.Close() }
    catch { $status.Text=$_.Exception.Message;$remove.Enabled=$true }
})
[void]$form.ShowDialog()
