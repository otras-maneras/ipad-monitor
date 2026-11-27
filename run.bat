@echo off
cd /d "%~dp0"

if not exist .venv (
  echo Creando entorno virtual...
  python -m venv .venv
)

call .venv\Scripts\activate.bat
pip install -r requirements.txt -q

echo.
python run.py
pause
