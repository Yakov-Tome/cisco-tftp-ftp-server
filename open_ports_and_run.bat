@echo off
cd /d "%~dp0"
title Cisco Server - Port Setup & Launch

:: Check for Administrator privileges
net session >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [ERROR] This script must run as Administrator!
    echo  Right-click the file and choose "Run as administrator"
    echo.
    pause
    exit /b 1
)

echo.
echo  ============================================
echo   Cisco Server - Port Cleanup ^& Launch
echo  ============================================
echo.

:: ── Kill any process using UDP 69 ────────────────────────────────────────────
echo  [1/5] Checking for processes using port 69 (TFTP)...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":69 "') do (
    if not "%%P"=="0" (
        echo  [!] Killing PID %%P on port 69...
        taskkill /PID %%P /F >nul 2>&1
        if errorlevel 1 (
            echo  [WARN] Could not kill PID %%P - may already be gone
        ) else (
            echo  [OK] PID %%P killed
        )
    )
)

:: ── Kill any process using TCP 21 ────────────────────────────────────────────
echo  [2/5] Checking for processes using port 21 (FTP)...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":21 "') do (
    if not "%%P"=="0" (
        echo  [!] Killing PID %%P on port 21...
        taskkill /PID %%P /F >nul 2>&1
        if errorlevel 1 (
            echo  [WARN] Could not kill PID %%P - may already be gone
        ) else (
            echo  [OK] PID %%P killed
        )
    )
)

:: Small wait to let ports free up
timeout /t 2 /nobreak >nul

:: ── Remove old firewall rules ─────────────────────────────────────────────────
echo  [3/5] Removing old firewall rules...
netsh advfirewall firewall delete rule name="CiscoServer_TFTP" >nul 2>&1
netsh advfirewall firewall delete rule name="CiscoServer_FTP" >nul 2>&1
netsh advfirewall firewall delete rule name="CiscoServer_FTP_Passive" >nul 2>&1
echo  [OK] Old rules cleared

:: ── Open firewall ports ───────────────────────────────────────────────────────
echo  [4/5] Opening firewall ports...

netsh advfirewall firewall add rule name="CiscoServer_TFTP" protocol=UDP dir=in localport=69 action=allow >nul
echo  [OK] UDP 69  (TFTP)

netsh advfirewall firewall add rule name="CiscoServer_FTP" protocol=TCP dir=in localport=21 action=allow >nul
echo  [OK] TCP 21  (FTP)

netsh advfirewall firewall add rule name="CiscoServer_FTP_Passive" protocol=TCP dir=in localport=60000-60100 action=allow >nul
echo  [OK] TCP 60000-60100  (FTP Passive)

:: ── Launch application ────────────────────────────────────────────────────────
echo  [5/5] Launching Cisco Server...
echo.

if exist "%~dp0dist\CiscoServer.exe" (
    start "" "%~dp0dist\CiscoServer.exe"
    goto :done
)
if exist "%~dp0CiscoServer.exe" (
    start "" "%~dp0CiscoServer.exe"
    goto :done
)
if exist "%~dp0cisco_server.py" (
    python "%~dp0cisco_server.py"
    goto :done
)

echo  [ERROR] Could not find CiscoServer.exe or cisco_server.py
pause
exit /b 1

:done
echo  ============================================
echo   Done! Cisco Server is running.
echo  ============================================
timeout /t 3 /nobreak >nul
