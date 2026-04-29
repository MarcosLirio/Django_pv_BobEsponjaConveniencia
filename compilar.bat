@echo off
REM ========================================================
REM Script de Compilacao - Gera Executavel com PyInstaller
REM ========================================================

setlocal EnableDelayedExpansion

set "PYINSTALLER_CMD=pyinstaller"
if exist ".venv\Scripts\pyinstaller.exe" (
    set "PYINSTALLER_CMD=.venv\Scripts\pyinstaller.exe"
)

echo.
echo ========================================================
echo COMPILADOR - Sistema de Vendas Bob Esponja
echo ========================================================
echo.

REM Verificar PyInstaller
"%PYINSTALLER_CMD%" --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] PyInstaller nao instalado!
    echo.
    echo Instale com: pip install pyinstaller
    echo Ou ative o ambiente virtual: .\.venv\Scripts\activate
    echo.
    pause
    exit /b 1
)

echo [1/3] Limpando compilacoes anteriores...
if exist build rmdir /s /q build >nul 2>&1
if exist dist rmdir /s /q dist >nul 2>&1

echo [2/3] Compilando executavel...
"%PYINSTALLER_CMD%" --onefile ^
    --windowed ^
    --name "SistemaVendas" ^
    --distpath "./dist" ^
    --workpath "./build" ^
    --specpath "." ^
    --hidden-import=django ^
    --hidden-import=django.contrib.auth ^
    --hidden-import=django.contrib.contenttypes ^
    --hidden-import=PIL ^
    --hidden-import=reportlab ^
    --collect-all django ^
    run_server.py

if errorlevel 1 (
    echo.
    echo [ERRO] Falha na compilacao!
    pause
    exit /b 1
)

echo [3/3] Finalizando...
echo.
echo ========================================================
echo SUCESSO! Seu executavel foi gerado:
echo.
echo   dist\SistemaVendas.exe
echo.
echo Use este arquivo com a pasta completa do projeto ou via instalador NSIS.
echo ========================================================
echo.
pause
