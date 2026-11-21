param([Parameter(Mandatory=$true)][string]$GamePath)
$ErrorActionPreference = 'Stop'
$game = (Resolve-Path -LiteralPath $GamePath).Path
if (!(Test-Path -LiteralPath (Join-Path $game 'hl.exe') -PathType Leaf) -or
    !(Test-Path -LiteralPath (Join-Path $game 'cstrike') -PathType Container)) {
    throw 'Select the Counter-Strike folder with hl.exe and cstrike.'
}
if (Get-Process hl -ErrorAction SilentlyContinue) {
    throw 'Close Counter-Strike before installing.'
}
$source = Join-Path $PSScriptRoot 'payload'
if (!(Test-Path -LiteralPath (Join-Path $source 'cstrike\maps\de_insomnia_project_t.bsp') -PathType Leaf)) {
    throw 'Extract the complete Insomnia archive before running the installer.'
}
$backup = Join-Path $game ('insomnia-backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
$files = @(Get-ChildItem -LiteralPath $source -File -Recurse)
$changes = [Collections.Generic.List[object]]::new()
try {
    foreach ($file in $files) {
        $relative = $file.FullName.Substring($source.Length + 1)
        $destination = Join-Path $game $relative
        $saved = Join-Path $backup $relative
        $hadFile = Test-Path -LiteralPath $destination -PathType Leaf
        if ($hadFile) {
            New-Item -ItemType Directory -Path (Split-Path -Parent $saved) -Force | Out-Null
            Copy-Item -LiteralPath $destination -Destination $saved
        }
        New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
        $changes.Add(@{ Destination=$destination; Backup=$saved; HadFile=$hadFile })
        Copy-Item -LiteralPath $file.FullName -Destination $destination -Force
        if ((Get-FileHash -LiteralPath $file.FullName).Hash -ne (Get-FileHash -LiteralPath $destination).Hash) {
            throw "Installed file did not verify: $relative"
        }
    }
} catch {
    for ($i = $changes.Count - 1; $i -ge 0; $i--) {
        $change = $changes[$i]
        if ($change.HadFile) {
            Copy-Item -LiteralPath $change.Backup -Destination $change.Destination -Force
        } elseif (Test-Path -LiteralPath $change.Destination -PathType Leaf) {
            Remove-Item -LiteralPath $change.Destination
        }
    }
    throw
}
Write-Host "Installed $($changes.Count) files. Launch PLAY_INSOMNIA_LOCAL.cmd in the CS folder."
Write-Host "Backup for replaced files: $backup"
