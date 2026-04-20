@echo off
setlocal
cd /d "%~dp0"

echo ==============================================
echo Preparando pacote offline do sistema
echo ==============================================

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

echo.
echo [1/3] Atualizando pasta offline_packages...
if not exist "offline_packages" mkdir "offline_packages"
"%PYTHON_EXE%" -m pip download -r requirements.txt -d offline_packages
if errorlevel 1 goto :error

echo.
echo [2/3] Validando projeto...
"%PYTHON_EXE%" manage.py check
if errorlevel 1 goto :error

echo.
echo [3/3] Pacote pronto.
echo Copie estes itens para a outra maquina:
echo - a pasta inteira do projeto
echo - a pasta offline_packages
echo - o instalador do Python 3
echo.
echo Depois execute instalar_offline.bat na maquina de destino.
goto :end

:error
echo.
echo Falha ao preparar o pacote offline.
echo Verifique o Python, o ambiente virtual e o acesso aos pacotes.
exit /b 1

:end
echo.
pause
endlocal