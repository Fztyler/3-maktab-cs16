@echo off
setlocal
cd /d "%~dp0"
tasklist /fi "imagename eq hl.exe" /nh | findstr /i /b "hl.exe" >nul
if not errorlevel 1 exit /b 2
start "" "%~dp0InsomniaLaunch.exe" -condebug -game cstrike -nofbo +sv_lan 1 +mp_consistency 0 +cl_lw 0 +maxplayers 16
