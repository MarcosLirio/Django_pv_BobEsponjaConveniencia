@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Ambiente virtual nao encontrado.
    echo Execute instalar_offline.bat antes de iniciar o sistema em rede local.
    pause
    exit /b 1
)

echo ==============================================
echo Iniciando sistema em rede local
echo ==============================================
echo Este modo permite acesso de outros computadores da mesma rede.
echo Confirme que o arquivo .env contem DJANGO_ALLOWED_HOSTS com o IP desta maquina.
echo Exemplo: DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost,192.168.0.10
echo.
echo Descubra o IP local com o comando ipconfig, se necessario.
echo Para encerrar, pressione CTRL + C nesta janela.
echo.

".venv\Scripts\python.exe" manage.py runserver 0.0.0.0:8000

echo.
pause
endlocal