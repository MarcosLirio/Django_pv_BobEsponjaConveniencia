@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Ambiente virtual nao encontrado.
    echo Execute instalar_offline.bat antes de iniciar o sistema em rede local.
    pause
    exit /b 1
)

set "PORT="
for %%P in (8000 8001 8002 8003 8004 8005 8006 8007 8008 8009 8010) do (
    netstat -ano | findstr /R /C:":%%P .*LISTENING" >nul
    if errorlevel 1 if not defined PORT set "PORT=%%P"
)
if not defined PORT set "PORT=8000"

echo ==============================================
echo Iniciando sistema em rede local
echo ==============================================
echo Este modo permite acesso de outros computadores da mesma rede.
echo Confirme que o arquivo .env contem DJANGO_ALLOWED_HOSTS com o IP desta maquina.
echo Exemplo: DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost,192.168.0.10
echo Modo estavel: autoreload desativado para evitar falhas de StatReloader.
echo Porta escolhida automaticamente: !PORT!
echo.
echo Descubra o IP local com o comando ipconfig, se necessario.
echo Abra nos outros computadores: http://IP_DA_MAQUINA:!PORT!
echo Para encerrar, pressione CTRL + C nesta janela.
echo.

".venv\Scripts\python.exe" manage.py runserver 0.0.0.0:!PORT! --noreload

echo.
pause
endlocal