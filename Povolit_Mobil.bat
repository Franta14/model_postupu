@echo off
echo Povoluji port 8000 ve Windows Firewall pro pristup z mobilu...
netsh advfirewall firewall add rule name="Allow Port 8000 (Model Postupu)" dir=in action=allow protocol=TCP localport=8000
echo.
echo Hotovo! Nyni by mela adresa v mobilu fungovat.
pause
