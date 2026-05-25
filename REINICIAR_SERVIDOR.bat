@echo off
setlocal
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -Verb RunAs -WindowStyle Hidden -FilePath '%~dp0reiniciar_rede_local.bat'"

endlocal
exit /b 0
