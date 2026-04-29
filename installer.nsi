; Instalador NSIS - Sistema de Vendas Bob Esponja Conveniência
; Compile com: makensis.exe installer.nsi

!include "MUI2.nsh"
!include "x64.nsh"

; Configurações básicas
Name "Sistema de Vendas - Bob Esponja"
OutFile "SistemaVendas_Instalador.exe"
InstallDir "$PROGRAMFILES\SistemaVendas"
InstallDirRegKey HKLM "Software\SistemaVendas" "InstallDir"

; Interface
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_LANGUAGE "PortugueseBR"

; Seção de instalação
Section "Instalar"
  SetOutPath "$INSTDIR"
  
  ; Copiar arquivos do projeto
  File /r ".\*.*"
  
  ; Remover pastas desnecessárias
  RMDir /r "$INSTDIR\.git"
  RMDir /r "$INSTDIR\.venv"
  RMDir /r "$INSTDIR\__pycache__"
  
  ; Criar diretório para venv
  CreateDirectory "$INSTDIR\.venv"
  
  ; Registrar no registro do Windows
  WriteRegStr HKLM "Software\SistemaVendas" "InstallDir" "$INSTDIR"
  
  ; Criar atalho no menu iniciar
  CreateDirectory "$SMPROGRAMS\Sistema de Vendas"
  CreateShortCut "$SMPROGRAMS\Sistema de Vendas\Iniciar Servidor.lnk" "$INSTDIR\dist\SistemaVendas.exe"
  CreateShortCut "$SMPROGRAMS\Sistema de Vendas\Desinstalar.lnk" "$INSTDIR\Uninstall.exe"
  
  ; Criar atalho na área de trabalho
  CreateShortCut "$DESKTOP\Sistema de Vendas.lnk" "$INSTDIR\dist\SistemaVendas.exe"
  
  ; Criar uninstaller
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  
SectionEnd

; Seção de desinstalação
Section "Uninstall"
  ; Remover atalhos
  Delete "$SMPROGRAMS\Sistema de Vendas\Iniciar Servidor.lnk"
  Delete "$SMPROGRAMS\Sistema de Vendas\Desinstalar.lnk"
  RMDir "$SMPROGRAMS\Sistema de Vendas"
  Delete "$DESKTOP\Sistema de Vendas.lnk"
  
  ; Remover registro
  DeleteRegKey HKLM "Software\SistemaVendas"
  
  ; Remover pasta de instalação
  RMDir /r "$INSTDIR"
  
SectionEnd
