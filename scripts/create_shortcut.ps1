# Creates a pinnable CurioPilot desktop shortcut
$root = Split-Path -Parent $PSScriptRoot
$vbs  = "$PSScriptRoot\launch.vbs"
$ico  = "$PSScriptRoot\curiopilot.ico"
$dest = [Environment]::GetFolderPath('Desktop') + "\CurioPilot.lnk"

$shell     = New-Object -ComObject WScript.Shell
$shortcut  = $shell.CreateShortcut($dest)

$shortcut.TargetPath       = "wscript.exe"
$shortcut.Arguments        = "`"$vbs`""
$shortcut.IconLocation     = "$ico,0"
$shortcut.Description      = "CurioPilot"
$shortcut.WorkingDirectory = $root

$shortcut.Save()

Write-Host "Shortcut created at: $dest"
Write-Host "Right-click it on your Desktop and choose 'Pin to taskbar'."
