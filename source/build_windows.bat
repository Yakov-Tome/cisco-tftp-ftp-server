@echo off
cd /d "%~dp0"
title Cisco Server Builder

echo.
echo  ============================================
echo   Cisco TFTP/FTP Server - Windows EXE Build
echo  ============================================
echo  Working directory: %CD%
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found. Install from https://python.org
    pause & exit /b 1
)

if not exist "cisco_server.py" (
    echo  [ERROR] cisco_server.py not found in %CD%
    pause & exit /b 1
)

echo  [1/3] Installing dependencies...
python -m pip install pyftpdlib tftpy pyinstaller --quiet

echo  [2/3] Building EXE...
set SCRIPT=%CD%\cisco_server.py
set DIST=%CD%\dist
set BUILD=%CD%\build

python -m PyInstaller --onefile --noconsole --name CiscoServer --distpath "%DIST%" --workpath "%BUILD%" --specpath "%CD%" "%SCRIPT%"

if errorlevel 1 (
    echo  [ERROR] Build failed
    pause & exit /b 1
)

echo.
echo  ============================================
echo   SUCCESS!  dist\CiscoServer.exe
echo  ============================================
pause
