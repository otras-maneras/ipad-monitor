# iPad Monitor - reiniciar el monitor virtual para aplicar cambios de vdd_settings.xml
# Uso: .\scripts\restart-virtual-display.ps1

$device = Get-PnpDevice | Where-Object {
    $_.FriendlyName -like "*Virtual Display*" -or
    $_.FriendlyName -like "*Virtual*Driver*"
} | Select-Object -First 1

if (-not $device) {
    Write-Host "No se encontro un dispositivo virtual." -ForegroundColor Red
    Write-Host "Buscando monitores genericos..." -ForegroundColor Yellow
    $device = Get-PnpDevice -Class Monitor | Where-Object {
        $_.FriendlyName -like "*Generic PnP*" -or
        $_.FriendlyName -like "*Monitor PnP*"
    } | Select-Object -First 1
}

if (-not $device) {
    Write-Host "No se encontro ningun dispositivo para reiniciar." -ForegroundColor Red
    exit 1
}

Write-Host "Dispositivo encontrado: $($device.FriendlyName)" -ForegroundColor Cyan
Write-Host "Deshabilitando..." -NoNewline
Disable-PnpDevice -InstanceId $device.InstanceId -Confirm:$false
Write-Host " OK"

Start-Sleep -Seconds 2

Write-Host "Habilitando..." -NoNewline
Enable-PnpDevice -InstanceId $device.InstanceId -Confirm:$false
Write-Host " OK"

Write-Host ""
Write-Host "El monitor virtual se reinicio." -ForegroundColor Green
Write-Host "Ahora abri Configuracion -> Sistema -> Pantalla y verifica que aparezca 1024x768."
exit 0
