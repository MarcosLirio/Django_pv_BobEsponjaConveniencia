@echo off
setlocal
cd /d "%~dp0"

echo ==============================================
echo Instalacao offline do sistema de vendas
echo ==============================================

where py >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON_CMD=py -3"
) else (
    set "PYTHON_CMD=python"
)

echo.
echo [1/5] Verificando Python...
%PYTHON_CMD% --version >nul 2>nul
if errorlevel 1 (
    echo Python 3 nao encontrado.
    echo Instale o Python 3 nesta maquina e rode novamente.
    goto :error
)

echo.
echo [2/5] Criando ambiente virtual...
if not exist ".venv\Scripts\python.exe" (
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 goto :error
)

set "VENV_PYTHON=.venv\Scripts\python.exe"

echo.
echo [3/5] Instalando dependencias...
if exist "offline_packages" (
    "%VENV_PYTHON%" -m pip install --no-index --find-links=offline_packages -r requirements.txt
) else (
    echo Pasta offline_packages nao encontrada.
    echo Coloque a pasta offline_packages ao lado deste projeto para instalar sem internet.
    goto :error
)
if errorlevel 1 goto :error

echo.
echo [4/5] Aplicando migracoes...
"%VENV_PYTHON%" manage.py migrate
if errorlevel 1 goto :error

echo.
echo [5/5] Conferindo o sistema...
"%VENV_PYTHON%" manage.py check
if errorlevel 1 goto :error

if not exist ".env" if exist ".env.example" (
    copy /Y ".env.example" ".env" >nul
)

echo.
echo Instalacao concluida com sucesso.
echo Para iniciar, execute iniciar_sistema_local.bat
goto :end

:error
echo.
echo A instalacao offline falhou.
exit /b 1

:end
echo.
pause
endlocal