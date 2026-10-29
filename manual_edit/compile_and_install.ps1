param([switch]$FullVis)
$ErrorActionPreference='Stop'
$mapRoot=$PSScriptRoot
$gameRoot='N:\Counter-Strike 1.6'
if(Get-Process hl -ErrorAction SilentlyContinue | Where-Object {$_.Path -eq "$gameRoot\hl.exe"}) {throw 'Close Counter-Strike before installing the edited map.'}
Push-Location -LiteralPath $mapRoot
try {
    $stamp=Get-Date -Format yyyyMMdd_HHmmss
    $backup=Join-Path $mapRoot "backups\$stamp"
    New-Item -ItemType Directory -Path $backup -Force | Out-Null
    Copy-Item -LiteralPath "$mapRoot\de_3_maktab.map" -Destination "$backup\de_3_maktab.map"
    foreach($stage in @('CSG','BSP','VIS','RAD')) {
        $compileArgs=@('de_3_maktab.map','-threads','8')
        if($stage -eq 'VIS' -and !$FullVis){$compileArgs+='-fast'}
        & "$mapRoot\compiler\sdHL${stage}_x64.exe" @compileArgs
        if($LASTEXITCODE -ne 0){throw "Compilation failed: $stage. Map was not installed."}
    }
    python "$mapRoot\share_window_models.py" "$mapRoot\de_3_maktab.map" "$mapRoot\de_3_maktab.bsp"
    if($LASTEXITCODE -ne 0){throw "Window model optimization failed. Map was not installed."}
    if(Test-Path "$gameRoot\cstrike\maps\de_3_maktab.bsp"){Copy-Item -LiteralPath "$gameRoot\cstrike\maps\de_3_maktab.bsp" -Destination "$backup\previous_installed.bsp"}
    if(Test-Path "$gameRoot\cstrike\maps\de_3_maktab.nav"){Move-Item -LiteralPath "$gameRoot\cstrike\maps\de_3_maktab.nav" -Destination "$backup\previous_installed.nav"}
    Copy-Item -LiteralPath "$mapRoot\de_3_maktab.bsp" -Destination "$gameRoot\cstrike\maps\de_3_maktab.bsp"
    Copy-Item -LiteralPath "$mapRoot\3_maktab.wad" -Destination "$gameRoot\cstrike\3_maktab.wad"
    Get-ChildItem -LiteralPath "$mapRoot\cstrike" -File -Recurse | ForEach-Object {
        $relative=$_.FullName.Substring(("$mapRoot\cstrike\").Length)
        $target=Join-Path "$gameRoot\cstrike" $relative
        New-Item -ItemType Directory -Path (Split-Path $target) -Force | Out-Null
        Copy-Item -LiteralPath $_.FullName -Destination $target
    }
    Write-Host 'Installed! Start de_3_maktab. Rebuild bot navigation after geometry edits.' -ForegroundColor Green
} finally {Pop-Location}
