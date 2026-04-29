@echo off
setlocal
cd /d "%~dp0"

echo ==============================================
echo Liberando portas 8000 a 8010 no Firewall do Windows
echo ==============================================
echo Execute este arquivo como Administrador.
echo.

net session >nul 2>nul
if not "%errorlevel%"=="0" (
    echo Este script precisa ser executado como Administrador.
    echo Clique com o botao direito e escolha "Executar como administrador".
    echo.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "if (-not (Get-NetFirewallRule -DisplayName 'Django8000a8010' -ErrorAction SilentlyContinue)) { New-NetFirewallRule -DisplayName 'Django8000a8010' -Direction Inbound -Protocol TCP -LocalPort 8000-8010 -Action Allow | Out-Null; Write-Host 'Regra criada com sucesso.' } else { Write-Host 'A regra Django8000a8010 ja existe.' }"

if errorlevel 1 (
    echo.
    echo Nao foi possivel criar a regra do firewall.
    pause
    exit /b 1
)

echo.
echo Portas 8000 a 8010 liberadas no firewall.
echo Agora execute iniciar_rede_local.bat e teste o acesso pelo IP desta maquina.
echo.
pause
endlocal