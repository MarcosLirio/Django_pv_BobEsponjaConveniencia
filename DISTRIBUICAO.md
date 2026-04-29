# Distribuição do Sistema - Guia de Criação do Instalador

## Opção 1: Usar o .bat Simples (Mais Fácil)

Se o usuário final tiver Python instalado, basta rodar:
```
run_server.bat
```

Isso:
1. Verifica se Python está disponível
2. Inicia o servidor automaticamente
3. Abre o navegador na porta disponível
4. Detecta rede local automaticamente

---

## Opção 2: Criar Executável com PyInstaller (Sem Necessidade de Python)

Se você quer distribuir para máquinas SEM Python instalado:

### Passo 1: Compilar o Executável
```powershell
pyinstaller --onefile --windowed --icon=icon.ico --name "SistemaVendas" run_server.py
```

Resultado: `dist\SistemaVendas.exe`

---

## Opção 3: Criar Instalador Profissional com NSIS (Recomendado)

Para distribuir como um instalador `.exe` profissional:

### Pré-requisitos:
1. Download NSIS: https://nsis.sourceforge.io/
2. Instale NSIS

### Passo 1: Preparar Arquivos
```powershell
# Executar do diretório do projeto
pyinstaller --onefile --windowed --icon=icon.ico --name "SistemaVendas" run_server.py
```

### Passo 2: Compilar Instalador
```powershell
makensis.exe installer.nsi
```

Resultado: `SistemaVendas_Instalador.exe`

### Passo 3: Distribuir
- Envie o arquivo `SistemaVendas_Instalador.exe` para o usuário
- O usuário executa, instala, e pronto
- Um atalho aparece na área de trabalho

---

## Fluxo do Usuário Final

1. Baixa `SistemaVendas_Instalador.exe`
2. Executa o instalador
3. Clica em "Instalar"
4. Um atalho aparece na área de trabalho e no menu iniciar
5. Clica no atalho, o servidor sobe e abre o navegador automaticamente

---

## Anatomia do Processo

```
Usuário Final
    ↓
Clica em SistemaVendas_Instalador.exe
    ↓
NSIS instala em C:\Program Files\SistemaVendas
    ↓
Cria atalho na Área de Trabalho
    ↓
Usuário clica no atalho
    ↓
run_server.exe inicia
    ↓
Detecta porta livre
    ↓
Abre navegador em http://127.0.0.1:PORT
    ↓
Sistema funcionando! 🎉
```

---

## Notas de Segurança

1. **Nunca distribua com dados sensíveis** — o banco vem limpo
2. **Arquivo .env não está incluído** — usuário configura credenciais locais
3. **Backup automático** — sistema cria backups na pasta `backups/`

---

## Comando Rápido (Tudo em um)

Se quiser automatizar tudo:

```powershell
# Compilar exe
pyinstaller --onefile --windowed --icon=icon.ico --name "SistemaVendas" run_server.py

# Compilar instalador (após instalar NSIS)
makensis.exe installer.nsi
```

Resultado final: `SistemaVendas_Instalador.exe` pronto para distribuir!
