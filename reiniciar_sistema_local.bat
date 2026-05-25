@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "PORT=8000"
echo ==============================================
echo Reiniciando servidor local do Sistema de Vendas
echo ==============================================
echo.

call parar_servidor_local.bat
if errorlevel 1 (
    echo Falha ao encerrar o servidor anterior.
    pause
    exit /b 1
)

echo Iniciando novamente em http://127.0.0.1:%PORT%
echo.
call iniciar_sistema_local.bat

endlocal
