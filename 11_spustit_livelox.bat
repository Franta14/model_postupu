@echo off
echo.
echo ==========================================================
echo          Spoustim Livelox Vizualizaci Postupu
echo ==========================================================
echo.
echo [1/3] Generuji nejnovejsi data z chvalenych postupu...
python 11_livelox_export.py
if errorlevel 1 (
    echo.
    echo CHYBA: Export dat selhal.
    pause
    exit /b
)

echo [2/3] Zpřístupňuji simulátor v prohlížeči...
start http://localhost:8080/export/livelox/index.html

echo.
echo ==========================================================
echo [3/3] Simulátor běží na adrese:
echo       http://localhost:8080/export/livelox/index.html
echo.
echo Klikni na odkaz výše se stisknutým CTRL, pokud se
echo okno prohlížeče neotevřelo automaticky.
echo.
echo Pro ukončení stiskni CTRL+C.
echo ==========================================================
echo.
python -m http.server 8080
