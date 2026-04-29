@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "PORT=8000"
echo ==============================================
echo Reiniciando servidor local do Sistema de Vendas
echo ==============================================
echo.

for /f "tokens=5" %%a in ('netstat -ano ^| findstr /R /C:":%PORT% .*LISTENING"') do (
    echo Encerrando processo PID %%a que estava usando a porta %PORT%...
    taskkill /PID %%a /F >nul 2>&1
)

echo Iniciando novamente em http://127.0.0.1:%PORT%
echo.
call iniciar_sistema_local.bat

endlocal
