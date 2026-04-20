@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Ambiente virtual nao encontrado.
    echo Execute instalar_offline.bat antes de limpar a base.
    pause
    exit /b 1
)

echo ==============================================
echo Limpando base para implantacao
echo ==============================================
echo Esta operacao remove categorias, produtos, vendas e usuarios,
echo preservando apenas o administrador Marcos.
echo Um backup do banco sera criado automaticamente na pasta backups.
echo.
set /p CONFIRMAR=Deseja continuar? Digite SIM para prosseguir: 
if /I not "%CONFIRMAR%"=="SIM" (
    echo Operacao cancelada.
    pause
    exit /b 0
)

".venv\Scripts\python.exe" manage.py reset_deployment_data --admin-username Marcos

echo.
pause
endlocal