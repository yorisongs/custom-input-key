# アイコン付きのショートカット「Custom Input Key.lnk」をこのフォルダとデスクトップに作る
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonw = (Get-Command pythonw).Source
$shell = New-Object -ComObject WScript.Shell
foreach ($target in @($dir, [Environment]::GetFolderPath("Desktop"))) {
    $lnk = $shell.CreateShortcut((Join-Path $target "Custom Input Key.lnk"))
    $lnk.TargetPath = $pythonw
    $lnk.Arguments = "`"$dir\CustomInputKey.pyw`""
    $lnk.WorkingDirectory = $dir
    $lnk.IconLocation = "$dir\app_icon.ico,0"
    $lnk.Save()
}
Write-Output "作成しました"
