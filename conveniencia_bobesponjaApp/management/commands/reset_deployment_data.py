from pathlib import Path
import shutil
from datetime import datetime

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from conveniencia_bobesponjaApp.models import Categorys, Products, Sales, Salesitems


class Command(BaseCommand):
    help = 'Limpa os dados operacionais e preserva apenas o usuario administrador informado.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--admin-username',
            default='Marcos',
            help='Nome de usuario que sera preservado como administrador.',
        )

    def handle(self, *args, **options):
        admin_username = options['admin_username'].strip()
        if not admin_username:
            raise CommandError('Informe um nome de usuario administrador valido.')

        admin_user = User.objects.filter(username=admin_username).first()
        if not admin_user:
            raise CommandError(f'O usuario {admin_username} nao foi encontrado. A limpeza foi cancelada.')

        backup_path = self._backup_database()

        with transaction.atomic():
            deleted_summary = {
                'salesitems': Salesitems.objects.count(),
                'sales': Sales.objects.count(),
                'products': Products.objects.count(),
                'categories': Categorys.objects.count(),
                'users_removed': User.objects.exclude(id=admin_user.id).count(),
            }

            Salesitems.objects.all().delete()
            Sales.objects.all().delete()
            Products.objects.all().delete()
            Categorys.objects.all().delete()
            User.objects.exclude(id=admin_user.id).delete()

            admin_user.is_superuser = True
            admin_user.is_staff = True
            admin_user.is_active = True
            admin_user.save(update_fields=['is_superuser', 'is_staff', 'is_active'])

            self._reset_sqlite_sequences()

        self.stdout.write(self.style.SUCCESS('Base limpa com sucesso para nova implantacao local.'))
        self.stdout.write(f'Backup criado em: {backup_path}')
        self.stdout.write(f'Administrador preservado: {admin_user.username}')
        self.stdout.write(f'Itens de venda removidos: {deleted_summary["salesitems"]}')
        self.stdout.write(f'Vendas removidas: {deleted_summary["sales"]}')
        self.stdout.write(f'Produtos removidos: {deleted_summary["products"]}')
        self.stdout.write(f'Categorias removidas: {deleted_summary["categories"]}')
        self.stdout.write(f'Usuarios removidos: {deleted_summary["users_removed"]}')

    def _backup_database(self):
        database_name = settings.DATABASES['default']['NAME']
        database_path = Path(database_name)
        if not database_path.exists():
            raise CommandError(f'Banco de dados nao encontrado em {database_path}.')

        backups_dir = Path(settings.BASE_DIR) / 'backups'
        backups_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = backups_dir / f'db_before_reset_{timestamp}.sqlite3'
        shutil.copy2(database_path, backup_path)
        return backup_path

    def _reset_sqlite_sequences(self):
        if connection.vendor != 'sqlite':
            return

        table_names = ['conveniencia_bobesponjaapp_salesitems', 'conveniencia_bobesponjaapp_sales', 'conveniencia_bobesponjaapp_products', 'conveniencia_bobesponjaapp_categorys']
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM sqlite_sequence WHERE name IN (%s)" % ','.join(['%s'] * len(table_names)),
                table_names,
            )