@echo off
setlocal
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -Verb RunAs -WindowStyle Hidden -FilePath '%~dp0parar_servidor_local.bat' -ArgumentList '--elevated'"

endlocal
exit /b 0
