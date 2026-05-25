import os
import sys
from django.utils import timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'conveniencia_bobesponja.settings')
import django
django.setup()

from conveniencia_bobesponjaApp.models import Sales

ids = [255, 259, 262, 267, 268]
qs = Sales.objects.filter(id__in=ids)
print('Deleting', qs.count(), 'sales with ids', ids)
for s in qs:
    print(' delete', s.id, s.comanda_code, s.customer_id, getattr(s.customer, 'name', None), s.status)
qs.delete()

remaining = Sales.objects.filter(status='OPEN').order_by('id')
print('Remaining open sales:', remaining.count())
for r in remaining:
    print(' remain', r.id, r.comanda_code, r.customer_id, getattr(r.customer, 'name', None), r.status)
