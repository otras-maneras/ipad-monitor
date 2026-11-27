@echo off
chcp 65001 >nul
echo iPad Monitor - reiniciar monitor virtual
echo =====================================
echo(
echo Esto deshabilita y vuelve a habilitar el monitor virtual
echo para que Windows lea el archivo vdd_settings.xml modificado.
echo(
powershell -ExecutionPolicy Bypass -File "%~dp0restart-virtual-display.ps1"
echo(
pause