@echo off
set "PATH=C:\Program Files\nodejs;%PATH%"
cd /d "%~dp0mobile_app"
echo ==========================================================
echo 📱 SPUSTENI EXPO MOBILNI APLIKACE (Scrollienteering)
echo ==========================================================
echo.
npx expo start -c
pause
