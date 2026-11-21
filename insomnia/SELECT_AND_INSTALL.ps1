$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
$folder = New-Object System.Windows.Forms.FolderBrowserDialog
$folder.Description = 'Select the separate Counter-Strike folder with hl.exe and cstrike'
try {
    if ($folder.ShowDialog() -eq 'OK') {
        & (Join-Path $PSScriptRoot 'INSTALL.ps1') -GamePath $folder.SelectedPath
    }
} finally {
    $folder.Dispose()
}
