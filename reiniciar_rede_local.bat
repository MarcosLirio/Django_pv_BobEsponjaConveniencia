@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo ==============================================
echo Reiniciando servidor em modo rede local
echo ==============================================
echo.

for %%P in (8000 8001 8002 8003 8004 8005 8006 8007 8008 8009 8010) do (
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr /R /C:":%%P .*LISTENING"') do (
        echo Encerrando PID %%a na porta %%P...
        taskkill /PID %%a /F >nul 2>&1
    )
)

echo Iniciando novamente em modo rede local...
echo.
call iniciar_rede_local.bat

endlocal
