@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Ambiente virtual nao encontrado.
    echo Execute instalar_offline.bat antes de iniciar o sistema.
    pause
    exit /b 1
)

echo ==============================================
echo Iniciando sistema local
echo ==============================================
echo Endereco local: http://127.0.0.1:8000
echo Modo estavel: autoreload desativado para evitar falhas de StatReloader.
echo Para encerrar, pressione CTRL + C nesta janela.
echo.

".venv\Scripts\python.exe" manage.py runserver 127.0.0.1:8000 --noreload

echo.
pause
endlocal