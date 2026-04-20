# Guia Offline

Este projeto pode rodar totalmente offline em outra maquina porque usa banco SQLite local no arquivo db.sqlite3.

## O que levar para a outra maquina

- a pasta inteira do projeto
- a pasta offline_packages
- o instalador do Python 3
- o arquivo .env, se voce usa configuracoes personalizadas

## Como preparar na maquina atual

1. Execute preparar_pacote_offline.bat.
2. Aguarde a criacao ou atualizacao da pasta offline_packages.
3. Copie o projeto completo para a outra maquina.

## Como instalar na outra maquina

1. Instale o Python 3.
2. Abra a pasta do projeto.
3. Execute instalar_offline.bat.
4. Se quiser iniciar com base limpa para implantacao, execute limpar_base_implantacao.bat.
5. Quando terminar, execute iniciar_sistema_local.bat.

## Como liberar para rede local sem internet

1. Descubra o IP da maquina principal com ipconfig.
2. No arquivo .env, ajuste DJANGO_ALLOWED_HOSTS com localhost, 127.0.0.1 e o IP da maquina.
3. Execute iniciar_rede_local.bat na maquina principal.
4. Nos outros computadores da mesma rede, abra http://IP_DA_MAQUINA:8000.

## Como acessar

- Na propria maquina: http://127.0.0.1:8000
- Em rede local: http://IP_DA_MAQUINA:8000

## Observacoes importantes

- Se voce quer manter os dados atuais, leve junto o arquivo db.sqlite3.
- Se voce quer iniciar com base zerada, use limpar_base_implantacao.bat. Ele apaga categorias, produtos, vendas e usuarios extras, mantendo apenas o administrador Marcos e criando um backup automatico em backups.
- Novos usuarios cadastrados no sistema entram como vendedores, sem permissao de administrador.
- O leitor de codigo de barras USB funciona como teclado e nao precisa de internet.
- Recuperacao de senha por e-mail depende de SMTP e pode nao funcionar sem rede.
- Para rede local, use iniciar_rede_local.bat e configure DJANGO_ALLOWED_HOSTS no arquivo .env.