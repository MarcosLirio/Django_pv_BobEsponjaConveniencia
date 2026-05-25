@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo ==============================================
echo Reiniciando servidor em modo rede local
echo ==============================================
echo.

call parar_servidor_local.bat
if errorlevel 1 (
    echo Falha ao encerrar o servidor anterior.
    pause
    exit /b 1
)

echo Iniciando novamente em modo rede local...
echo.
call iniciar_rede_local.bat

endlocal
