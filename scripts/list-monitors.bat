@echo off
chcp 65001 >nul
echo iPad Monitor - monitores detectados por Windows
echo =============================================
echo(
powershell -ExecutionPolicy Bypass -File "%~dp0list-monitors.ps1"
echo(
if %errorlevel% neq 0 (
  echo No se detectaron monitores con ningun metodo.
)
pause