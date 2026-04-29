#!/usr/bin/env python
"""
Servidor Django - Sistema de Vendas Bob Esponja
Inicia o servidor fixo na porta 8000.
"""
import os
import sys
import socket
import subprocess
import webbrowser
from pathlib import Path
from time import sleep


def is_port_in_use(port=8000):
    """Verifica se a porta ja esta em uso."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(('127.0.0.1', port)) == 0


def get_local_ip():
    """Obtém o IP local da máquina."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(('8.8.8.8', 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except Exception:
        return '192.168.x.x'


def main():
    base_dir = Path(__file__).resolve().parent
    os.chdir(base_dir)

    manage_py = base_dir / 'manage.py'
    if not manage_py.exists():
        print('=' * 60)
        print('ERRO: arquivo manage.py nao encontrado.')
        print('Este executavel funciona junto com a pasta completa do projeto.')
        print(f'Caminho atual: {base_dir}')
        print('=' * 60)
        sys.exit(1)
    
    # Configurar variáveis de ambiente
    if not os.getenv('DJANGO_SETTINGS_MODULE'):
        os.environ['DJANGO_SETTINGS_MODULE'] = 'conveniencia_bobesponja.settings'
    
    # Porta fixa para manter compatibilidade com atalhos e clientes
    port = 8000
    if is_port_in_use(port):
        print('=' * 60)
        print('ERRO: A porta 8000 ja esta em uso.')
        print('Feche o processo em execucao e tente novamente.')
        print('=' * 60)
        sys.exit(1)

    local_ip = get_local_ip()
    
    # Exibir informações
    print('=' * 60)
    print('SISTEMA DE VENDAS - Bob Esponja Conveniência')
    print('=' * 60)
    print(f'\n✓ Servidor iniciando na porta {port}...\n')
    print(f'Local:      http://127.0.0.1:{port}')
    print(f'Rede local: http://{local_ip}:{port}')
    print('\nPressione CTRL+C para encerrar o servidor.\n')
    print('=' * 60 + '\n')
    
    # Aguardar um pouco antes de abrir o navegador
    sleep(2)
    
    # Abrir navegador automaticamente
    try:
        webbrowser.open(f'http://127.0.0.1:{port}/login')
    except Exception as e:
        print(f'Não foi possível abrir o navegador: {e}')
    
    # Executar servidor Django
    try:
        cmd = [sys.executable, str(manage_py), 'runserver', f'0.0.0.0:{port}', '--noreload']
        subprocess.run(cmd, check=False)
    except KeyboardInterrupt:
        print('\n\nServidor encerrado pelo usuário.')
    except Exception as e:
        print(f'Erro ao iniciar o servidor: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()
