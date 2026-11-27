@echo off
chcp 65001 >nul
echo iPad Monitor - forzar resolucion del monitor virtual a 1024x768
echo =========================================================
echo(
echo Esto busca un monitor con "Virtual" en el nombre
echo y trata de cambiarlo a 1024x768.
echo(
powershell -ExecutionPolicy Bypass -File "%~dp0set-resolution.ps1" -Name "Virtual"
if %errorlevel% neq 0 (
  echo(
  echo No se pudo cambiar la resolucion automaticamente.
)
pause