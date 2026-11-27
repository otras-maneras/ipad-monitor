# iPad Monitor: arranca el emisor H.264 por Wi-Fi y USB y muestra la IP y el PIN.
# Lo abre el acceso directo "iPad Monitor" que crea install-windows.bat.
$ErrorActionPreference = 'Stop'
$Root = Resolve-Path (Join-Path $PSScriptRoot '..\..')
Set-Location $Root
$Host.UI.RawUI.WindowTitle = 'iPad Monitor'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$env:PYTHONIOENCODING = 'utf-8'

function Stop-WithMessage($Message) {
    Write-Host ''
    Write-Host $Message -ForegroundColor Yellow
    Read-Host 'Presioná Enter para cerrar esta ventana'
    exit 1
}

$Python = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) { Stop-WithMessage 'Falta el entorno de Python. Ejecutá install-windows.bat.' }
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Stop-WithMessage 'Falta FFmpeg en el PATH. Ejecutá install-windows.bat.'
}

# IP de la interfaz con puerta de enlace (la red por la que llega el iPad).
$Ip = Get-NetIPConfiguration |
    Where-Object { $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq 'Up' } |
    ForEach-Object { $_.IPv4Address.IPAddress } |
    Select-Object -First 1
if (-not $Ip) { Stop-WithMessage 'No hay conexión de red. Conectá la PC al Wi-Fi y volvé a abrir iPad Monitor.' }

# El monitor virtual de 1024x768 si existe; si no, el principal en espejo.
# Comillas simples: PowerShell 5.1 quita las dobles al pasar argumentos a un .exe.
$Pick = @'
from server.screen_capture import list_monitors
monitors = [m for m in list_monitors() if m['id'] > 0]
ipad = [m['id'] for m in monitors
        if (m['width'], m['height']) == (1024, 768) and not m.get('is_primary')]
primary = [m['id'] for m in monitors if m.get('is_primary')] or [monitors[0]['id']]
print(ipad[-1] if ipad else primary[0], 1 if ipad else 0)
'@
$Choice = "$(& $Python -B -c $Pick 2>$null | Select-Object -Last 1)".Trim() -split ' '
$Monitor = if ($Choice[0]) { $Choice[0] } else { '1' }
$Extended = $Choice[1] -eq '1'

Clear-Host
Write-Host '=============================================='
Write-Host '  iPad Monitor · pantalla para el iPad'
Write-Host '=============================================='
if ($Extended) { Write-Host "  Modo:  pantalla extendida (monitor $Monitor)" }
else { Write-Host '  Modo:  espejo de la pantalla principal' }
Write-Host '  En el iPad: Wi-Fi → Mac → Address'
Write-Host "  IP:    $Ip"
Write-Host '  Para USB: conectá el cable y elegí USB'
Write-Host '  en el panel del visor.'
Write-Host '  El PIN aparece abajo. Un iPad ya emparejado'
Write-Host '  entra sin PIN.'
Write-Host '  Para terminar, cerrá esta ventana.'
Write-Host '=============================================='
Write-Host ''

$LogDir = Join-Path $env:LOCALAPPDATA 'ipad-monitor'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Log = Join-Path $LogDir 'emisor.log'
Add-Content -Path $Log -Value ('--- ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ---') -Encoding UTF8

$ErrorActionPreference = 'Continue'
& $Python -B -m server.ipadscreen_h264 --bind $Ip --usb --monitor $Monitor 2>&1 |
    ForEach-Object {
        $line = "$_"
        Write-Host $line
        Add-Content -Path $Log -Value $line -Encoding UTF8
    }
if ($LASTEXITCODE -ne 0) { Stop-WithMessage "El emisor terminó con un error. Registro: $Log" }
