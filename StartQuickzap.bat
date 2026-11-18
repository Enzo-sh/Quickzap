@echo off
setlocal
cd /d "%~dp0"
title Quickzap

python -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)" >nul 2>nul
if errorlevel 1 goto nopython

python -m quickzap
if errorlevel 1 (
  echo.
  echo Quickzap closed with an error. Check the message above.
  pause
)
goto :eof

:nopython
echo Quickzap requires Python 3.9 or later, which was not found on this computer.
echo.
where winget >nul 2>nul
if errorlevel 1 goto manual
set /p ANSWER=Do you want to install Python now with winget? (Y/N): 
if /i not "%ANSWER%"=="Y" goto manual
winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
echo.
echo Done. Close this window and reopen StartQuickzap.bat.
pause
goto :eof

:manual
echo Download Python from https://www.python.org/downloads/
echo (check the "Add python.exe to PATH" box) and reopen this file.
start "" https://www.python.org/downloads/
pause
