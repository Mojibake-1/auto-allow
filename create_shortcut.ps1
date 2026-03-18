# 创建桌面快捷方式（指向 VBS 启动器，看起来像独立应用）
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$iconPath = Join-Path $scriptDir "icon.ico"
$vbsPath = Join-Path $scriptDir "AutoAllow.vbs"
$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktopPath "Auto Allow.lnk"

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($shortcutPath)
$Shortcut.TargetPath = $vbsPath
$Shortcut.WorkingDirectory = $scriptDir
$Shortcut.Description = "Auto Allow 屏幕精灵 - 自动点击"
if (Test-Path $iconPath) {
    $Shortcut.IconLocation = "$iconPath,0"
}
$Shortcut.Save()

Write-Host "Shortcut created: $shortcutPath"
