@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Ambiente virtual nao encontrado.
    echo Execute instalar_offline.bat antes de iniciar o sistema em rede local.
    pause
    exit /b 1
)

set "PORT=8000"
set "HTTPS_SCRIPT=C:\ProgramData\SistemaVendas\scripts\iniciar_sistema_https_global.bat"
set "PORT_PID="
for /f "tokens=5" %%a in ('netstat -ano ^| findstr /R /C:":%PORT% .*LISTENING"') do (
    set "PORT_PID=%%a"
    goto :port_check_done
)

:port_check_done
if defined PORT_PID (
    echo Porta %PORT% em uso pelo PID !PORT_PID!. Tentando liberar...
    call parar_servidor_local.bat
    if errorlevel 1 (
        echo.
        echo Nao foi possivel liberar a porta %PORT% automaticamente.
        echo Execute este script como Administrador ou libere a porta manualmente.
        echo.
        pause
        exit /b 1
    )
)

echo ==============================================
echo Iniciando sistema em rede local (HTTPS)
echo ==============================================
echo Este modo permite acesso de outros computadores da mesma rede com criptografia.
echo Confirme que o arquivo .env contem DJANGO_ALLOWED_HOSTS com o IP desta maquina.
echo Exemplo: DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost,192.168.0.10
echo Porta fixa: !PORT! (HTTPS)
echo.
echo Descubra o IP local com o comando ipconfig, se necessario.
echo Abra nos outros computadores: https://IP_DA_MAQUINA:!PORT!/login
echo Para encerrar, pressione CTRL + C nesta janela.
echo.
if not exist "!HTTPS_SCRIPT!" (
    echo ERRO: Script HTTPS global nao encontrado em:
    echo !HTTPS_SCRIPT!
    pause
    exit /b 1
)

call "!HTTPS_SCRIPT!"

echo.
start "" powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "C:\ProgramData\SistemaVendas\scripts\mostrar_notificacao.ps1" -Title "Sistema de Vendas" -Message "Servidor de rede local desativado."
pause
endlocal