@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

if not exist "manage.py" (
    echo ERRO: Arquivo manage.py nao encontrado em:
    echo !cd!
    echo.
    echo Verifique se este atalho aponta para a pasta correta do projeto.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Ambiente virtual nao encontrado.
    echo Execute instalar_offline.bat antes de iniciar o sistema.
    pause
    exit /b 1
)

set "PORT=8000"

netstat -ano | findstr /R /C:":%PORT% .*LISTENING" >nul
if not errorlevel 1 (
    echo Porta %PORT% em uso. Tentando reiniciar o servidor automaticamente...
    call parar_servidor_local.bat
    if errorlevel 1 (
        echo ERRO: Nao foi possivel liberar a porta %PORT%.
        echo Execute este script como Administrador e tente novamente.
        pause
        exit /b 1
    )
)

echo ==============================================
echo Iniciando sistema local
echo ==============================================
echo Endereco local: http://127.0.0.1:!PORT!
echo Rede local: http://0.0.0.0:!PORT!
echo Modo estavel: autoreload desativado para evitar falhas de StatReloader.
echo Para encerrar, pressione CTRL + C nesta janela.
echo.

".venv\Scripts\python.exe" manage.py runserver 0.0.0.0:!PORT! --noreload

echo.
pause
endlocal