# Instalador de iPad Monitor para Windows: Python, FFmpeg, entorno y acceso directo.
# Lo ejecuta install-windows.bat.
$ErrorActionPreference = 'Stop'
$Root = Resolve-Path (Join-Path $PSScriptRoot '..\..')
Set-Location $Root
[Console]::OutputEncoding = [Text.Encoding]::UTF8

function Ask($Question) {
    $answer = Read-Host "$Question [s/N]"
    return $answer -match '^[sSyY]'
}

function Update-Path {
    # winget agrega programas al PATH del sistema; esta ventana no lo ve sin recargarlo.
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
                [Environment]::GetEnvironmentVariable('Path', 'User')
}

function Install-WithWinget($Id, $Name) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Write-Host "Instalá $Name a mano y volvé a ejecutar este instalador." -ForegroundColor Yellow
        exit 1
    }
    winget install --id $Id -e --accept-package-agreements --accept-source-agreements
    Update-Path
}

Write-Host '== iPad Monitor para Windows =='

# 1. Python 3.11 o posterior
$Py = $null
foreach ($candidate in @('py', 'python')) {
    if (Get-Command $candidate -ErrorAction SilentlyContinue) {
        $version = & $candidate -c 'import sys; print(sys.version_info >= (3, 11))' 2>$null
        if ($version -eq 'True') { $Py = $candidate; break }
    }
}
if (-not $Py) {
    Write-Host 'Falta Python 3.11 o posterior.'
    if (Ask '¿Instalarlo con winget?') { Install-WithWinget 'Python.Python.3.12' 'Python' ; $Py = 'py' }
    else { exit 1 }
}

# 2. FFmpeg
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Host 'Falta FFmpeg.'
    if (Ask '¿Instalarlo con winget?') { Install-WithWinget 'Gyan.FFmpeg' 'FFmpeg' }
    else { exit 1 }
    if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
        Write-Host 'FFmpeg quedó instalado, pero esta ventana todavía no lo ve. Cerrala y volvé a ejecutar el instalador.' -ForegroundColor Yellow
        exit 1
    }
}

# 3. Entorno de Python
if (-not (Test-Path '.venv\Scripts\python.exe')) {
    Write-Host 'Creando el entorno de Python en .venv...'
    & $Py -m venv .venv
}
& '.venv\Scripts\python.exe' -m pip install -q -r requirements.txt

# 4. Accesos directos en el escritorio y en el menú Inicio
$Shell = New-Object -ComObject WScript.Shell
$Targets = @(
    [Environment]::GetFolderPath('Desktop'),
    (Join-Path ([Environment]::GetFolderPath('StartMenu')) 'Programs')
)
foreach ($folder in $Targets) {
    $link = $Shell.CreateShortcut((Join-Path $folder 'iPad Monitor.lnk'))
    $link.TargetPath = (Get-Command powershell).Source
    $link.Arguments = '-NoProfile -ExecutionPolicy Bypass -File "' + (Join-Path $Root 'scripts\windows\ipad-monitor.ps1') + '"'
    $link.WorkingDirectory = "$Root"
    $link.IconLocation = "$env:SystemRoot\System32\imageres.dll,109"
    $link.Description = 'Usar el iPad como pantalla por Wi-Fi o USB'
    $link.Save()
}
Write-Host 'Acceso directo "iPad Monitor" creado en el escritorio y en el menú Inicio.'

# 5. Monitor virtual (opcional)
Write-Host ''
Write-Host 'Para usar el iPad como pantalla extendida, Windows necesita un monitor virtual de 1024x768.'
if (Ask '¿Instalar Virtual Display Driver con winget?') {
    Install-WithWinget 'VirtualDrivers.Virtual-Display-Driver' 'Virtual Display Driver'
    Write-Host 'Configurá el monitor virtual en 1024x768 y extendé el escritorio con Win + P.'
    Write-Host 'Si no aparece esa resolución, ejecutá scripts\set-resolution.bat como administrador.'
}

Write-Host ''
Write-Host 'USB: requiere iTunes o el servicio Apple Mobile Device.'
Write-Host 'La primera vez, Windows puede pedir permiso de red para Python: permití redes privadas.'
Write-Host 'Instalación terminada. Abrí "iPad Monitor" desde el escritorio.'
