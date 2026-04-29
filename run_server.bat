@echo off
setlocal EnableDelayedExpansion

REM Script de inicializacao do Sistema de Vendas
REM Este arquivo inicia o servidor Django automaticamente

cd /d "%~dp0"

set "PYTHON_CMD="
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_CMD=.venv\Scripts\python.exe"
) else (
    py -3 --version >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_CMD=py -3"
    ) else (
        python --version >nul 2>&1
        if not errorlevel 1 set "PYTHON_CMD=python"
    )
)

REM Verificar se o Python esta disponivel
if not defined PYTHON_CMD (
    echo.
    echo ============================================================
    echo ERRO: Python nao foi encontrado no sistema
    echo ============================================================
    echo.
    echo Certifique-se de que:
    echo 1. A pasta .venv existe neste projeto, ou
    echo 2. Python 3.12+ esta instalado e no PATH
    echo.
    pause
    exit /b 1
)

REM Executar o servidor
%PYTHON_CMD% run_server.py
pause
