import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','conveniencia_bobesponja.settings')
import django
django.setup()
from conveniencia_bobesponjaApp.models import Sales

print('Últimas 20 vendas:')
for s in Sales.objects.all().order_by('-date_added')[:20]:
    print(f"ID:{s.id} code:{s.code} comanda:{s.comanda_code!r} status:{s.status} user:{s.user.username if s.user else None} customer:{s.customer.id if s.customer else None} customer_name:{s.customer.name if s.customer else ''} grand_total:{s.grand_total} date:{s.date_added}")
