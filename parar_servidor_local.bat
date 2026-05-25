@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

if /I "%~1"=="--elevated" goto :continue

net session >nul 2>nul
if not "%errorlevel%"=="0" (
    echo Este comando precisa de permissao de Administrador para encerrar o servidor antigo.
    echo Solicitando elevacao do Windows...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath $env:ComSpec -ArgumentList '/c """%~f0"" --elevated' -Verb RunAs -Wait"
    exit /b %errorlevel%
)

:continue

set "PROJECT_DIR=%cd%"
set "PORTS=8000 8001 8002 8003 8004 8005 8006 8007 8008 8009 8010"

echo ==============================================
echo Encerrando servidor local/rede do Sistema
echo ==============================================

REM 1) Encerra processos que estao escutando nas portas do sistema
for %%P in (%PORTS%) do (
    for /f "tokens=5" %%A in ('netstat -ano ^| findstr /R /C:":%%P .*LISTENING"') do (
        echo [Porta %%P] Encerrando PID %%A...
        taskkill /PID %%A /T /F >nul 2>&1
    )
)

REM 2) Encerra processos Python/Uvicorn associados ao servidor do sistema
for /f "tokens=2 delims==" %%L in ('wmic process where "(name='python.exe' or name='pythonw.exe' or name='uvicorn.exe') and (CommandLine like '%%manage.py runserver%%' or CommandLine like '%%run_https_server.py%%' or CommandLine like '%%conveniencia_bobesponja.asgi:application%%')" get ProcessId /value 2^>nul ^| findstr /I "ProcessId="') do (
    if not "%%L"=="" (
        echo [Processo] Encerrando PID %%L...
        taskkill /PID %%L /T /F >nul 2>&1
    )
)

REM 3) Aguarda alguns segundos para liberar sockets
for /l %%I in (1,1,5) do (
    >nul timeout /t 1
)

REM 4) Validacao final
set "HAS_PORT=0"
for %%P in (%PORTS%) do (
    netstat -ano | findstr /R /C:":%%P .*LISTENING" >nul
    if not errorlevel 1 (
        set "HAS_PORT=1"
    )
)

if "!HAS_PORT!"=="1" (
    echo.
    echo AVISO: Ainda existe processo escutando em alguma porta do sistema.
    echo Execute este script como Administrador e tente novamente.
    echo.
    exit /b 1
)

echo.
echo Servidor encerrado com sucesso.
exit /b 0
