@echo off
setlocal
cd /d "%~dp0"
title Quickzap

python -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)" >nul 2>nul
if errorlevel 1 goto nopython

python -m quickzap
if errorlevel 1 (
  echo.
  echo Quickzap se cerro con un error. Revisa el mensaje de arriba.
  pause
)
goto :eof

:nopython
echo Quickzap necesita Python 3.9 o superior y no se encontro en este equipo.
echo.
where winget >nul 2>nul
if errorlevel 1 goto manual
set /p ANSWER=Quieres instalar Python ahora con winget? (S/N): 
if /i not "%ANSWER%"=="S" goto manual
winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
echo.
echo Listo. Cierra esta ventana y vuelve a abrir Iniciar-Quickzap.bat.
pause
goto :eof

:manual
echo Descarga Python desde https://www.python.org/downloads/
echo (marca la casilla "Add python.exe to PATH") y vuelve a abrir este archivo.
start "" https://www.python.org/downloads/
pause
