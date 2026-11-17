param([string]$Python, [switch]$Restore, [switch]$ShortcutOnly)
$ErrorActionPreference='Stop'
$root=$PSScriptRoot
$sh=New-Object -ComObject WScript.Shell
$desktop=[Environment]::GetFolderPath('DesktopDirectory')
$target=Join-Path $desktop 'DaVinci Resolve.lnk'
$data=Join-Path $env:APPDATA 'ResolveEditTracker'
New-Item -ItemType Directory -Path $data -Force | Out-Null
$backup=Join-Path $data 'DaVinci Resolve.original.lnk'
# Upgrade-only cleanup: exact task names used by earlier development builds.
$sid=[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
foreach ($legacy in @('CutSync Resolve launcher', "CutSync Linked - $sid")) {
 if (Get-ScheduledTask -TaskName $legacy -ErrorAction SilentlyContinue) { Unregister-ScheduledTask -TaskName $legacy -Confirm:$false }
}
if ($Restore -or $ShortcutOnly) {
 $sid=[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
 $taskName="Stintory Linked - $sid"
 if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) { Unregister-ScheduledTask -TaskName $taskName -Confirm:$false }
 if($ShortcutOnly) { Write-Host "Periodic check disabled. The linked desktop shortcut still works."; exit 0 }
 if(Test-Path $target){$l=$sh.CreateShortcut($target); if(($l.Arguments -like '*launch_with_resolve.vbs*' -or $l.Arguments -like '*launch_resolve.pyw*')){if(Test-Path $backup){Copy-Item $backup $target -Force}else{Remove-Item $target}}}
 Write-Host 'Original desktop shortcut restored (if present).'; exit 0
}
if (!(Test-Path $Python -PathType Leaf)) {throw 'pythonw.exe not found'}
$resolve=$null; $argsOriginal=''; $work=''; $icon=''
$existing=if(Test-Path $backup){$backup}elseif(Test-Path $target){$target}else{$null}
if($existing){$l=$sh.CreateShortcut($existing); if([IO.Path]::GetFileName($l.TargetPath) -ieq 'Resolve.exe' -and (Test-Path $l.TargetPath)){ $resolve=$l.TargetPath; $argsOriginal=$l.Arguments; $work=$l.WorkingDirectory; $icon=$l.IconLocation; if(!(Test-Path $backup)){Copy-Item $existing $backup}}elseif(!(Test-Path $backup) -and ($l.Arguments -notlike '*launch_with_resolve.vbs*' -and $l.Arguments -notlike '*launch_resolve.pyw*')){throw 'Existing DaVinci Resolve shortcut has an unexpected target; not overwriting it.'}}
if(!$resolve){$resolve=Join-Path $env:ProgramFiles 'Blackmagic Design\DaVinci Resolve\Resolve.exe'}
if(!(Test-Path $resolve)){Add-Type -AssemblyName System.Windows.Forms; $dialog=New-Object Windows.Forms.OpenFileDialog; $dialog.Filter='Resolve.exe|Resolve.exe'; $dialog.Title='Select DaVinci Resolve executable'; if($dialog.ShowDialog() -ne 'OK'){throw 'Resolve selection cancelled'}; $resolve=$dialog.FileName}
if(!$work){$work=Split-Path $resolve}; if(!$icon -or $icon -eq ',0'){$icon="$resolve,0"}
@($resolve,$Python,(' '+$argsOriginal),$work) | Set-Content -LiteralPath (Join-Path $root 'launcher-config.txt') -Encoding Unicode
$l=$sh.CreateShortcut($target); $l.TargetPath=$Python; $l.Arguments='-E "'+(Join-Path $root 'launch_resolve.pyw')+'"'; $l.WorkingDirectory=$root; $l.IconLocation=$icon; $l.Description='DaVinci Resolve + Stintory'; $l.Save()
Write-Host "Linked: $target"
Write-Host 'Use this desktop icon. Re-pin it if you use the taskbar. Other launch paths use the scheduled check after setup.'
