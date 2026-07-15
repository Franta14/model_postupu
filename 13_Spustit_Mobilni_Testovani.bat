@echo off
cd /d "%~dp0"
echo ==========================================================
echo 📱 SPUSTENI MOBILNIHO TESTOVANI
echo ==========================================================
echo.

:: Spustíme lokální server ve vlastním novém okně
echo 1) Spoustim lokalni webovy server (vicevlaknovy pro rychlejsi nacitani dlazdic)...
start "Lokalni Web Server" cmd /c "cd export && python -c ""import http.server; http.server.test(HandlerClass=http.server.SimpleHTTPRequestHandler, ServerClass=http.server.ThreadingHTTPServer, port=8000, bind='0.0.0.0')"""

:: Spustíme Cloudflare tunel v tomto hlavním okně
echo 2) Vytvarim zabezpeceny tunel pres Cloudflare...
echo.
echo ==========================================================
echo HLEDEJ RADEK ZACINAJICI NA "https://" A KONCICI NA ".trycloudflare.com"
echo Tuto adresu si otevri na mobilu!
echo ==========================================================
echo.
.\cloudflared.exe tunnel --url http://localhost:8000

pause
