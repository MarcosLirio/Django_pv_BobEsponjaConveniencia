# Guia Offline

Este projeto pode rodar totalmente offline em outra maquina porque usa banco SQLite local no arquivo db.sqlite3.

## O que levar para a outra maquina

- a pasta inteira do projeto
- a pasta offline_packages
- o instalador do Python 3
- o arquivo .env, se voce usa configuracoes personalizadas
- nao reaproveite a pasta .venv de outro computador; o instalador offline recria isso na maquina de destino

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

Se a pasta .venv tiver vindo copiada de outro computador, o instalador agora apaga e recria automaticamente esse ambiente virtual.
Os arquivos de inicializacao usam modo estavel sem autoreload, para evitar falhas do StatReloader em maquinas de implantacao.

## Como liberar para rede local sem internet

1. Descubra o IP da maquina principal com ipconfig.
2. No arquivo .env, ajuste DJANGO_ALLOWED_HOSTS com localhost, 127.0.0.1 e o IP da maquina.
3. Se a maquina principal abrir o sistema localmente mas os outros computadores nao acessarem, execute liberar_porta_8000_firewall.bat como Administrador.
4. Execute iniciar_rede_local.bat na maquina principal.
5. Nos outros computadores da mesma rede, abra o endereco exibido pelo script, por exemplo http://IP_DA_MAQUINA:8000 ou http://IP_DA_MAQUINA:8001.

## Como acessar

- Na propria maquina: use o endereco exibido pelo script, como http://127.0.0.1:8000 ou http://127.0.0.1:8001
- Em rede local: use o endereco exibido pelo script, como http://IP_DA_MAQUINA:8000 ou http://IP_DA_MAQUINA:8001

## Observacoes importantes

- Se voce quer manter os dados atuais, leve junto o arquivo db.sqlite3.
- Se voce quer iniciar com base zerada, use limpar_base_implantacao.bat. Ele apaga categorias, produtos, vendas e usuarios extras, mantendo apenas o administrador Marcos e criando um backup automatico em backups.
- Novos usuarios cadastrados no sistema entram como vendedores, sem permissao de administrador.
- O leitor de codigo de barras USB funciona como teclado e nao precisa de internet.
- Recuperacao de senha por e-mail depende de SMTP e pode nao funcionar sem rede.
- Em uma base nova (sem usuarios), a tela de login exibe o botao para criar a conta inicial, que ja nasce como administrador.
- Para rede local, use iniciar_rede_local.bat e configure DJANGO_ALLOWED_HOSTS no arquivo .env.
- Se a porta 8000 estiver ocupada por outro programa ou por outra sessao do Windows, os scripts agora escolhem automaticamente a primeira porta livre entre 8000 e 8010.
- Se a maquina principal abre pelo IP e os outros computadores nao acessam, o problema costuma ser firewall do Windows ou isolamento da rede Wi-Fi.

## Checklist HTTPS antes do push

1. Defina DJANGO_DEBUG=False no arquivo .env do servidor de producao.
2. Defina DJANGO_DEFAULT_SCHEME=https no arquivo .env.
3. Defina DJANGO_FORCE_HTTPS=True apenas quando o servidor/proxy ja tiver certificado SSL valido.
4. Confira DJANGO_ALLOWED_HOSTS com o dominio final da aplicacao.
5. Se usar dominio adicional, preencha DJANGO_CSRF_TRUSTED_ORIGINS com origens completas separadas por virgula, por exemplo https://app.seudominio.com,https://painel.seudominio.com.
6. Valide login, logout e recuperacao de senha em ambiente de homologacao com HTTPS.
7. Execute o comando de validacao: .venv\Scripts\python.exe manage.py check.
8. Confirme que o arquivo .env nao sera publicado no GitHub.