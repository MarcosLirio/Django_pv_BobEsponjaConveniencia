import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','conveniencia_bobesponja.settings')
django.setup()

from conveniencia_bobesponjaApp.models import Sales

# Verificar Jansen
jansen = Sales.objects.get(id=301)
print("JANSEN:")
for item in jansen.salesitems_set.all():
    total = float(item.price) * int(item.qty)
    print(f"  {int(item.qty)}x {item.product_id.name} @ R${float(item.price):.2f} = R${total:.2f}")
print(f"Grand Total: R${float(jansen.grand_total):.2f}")
print()

# Verificar Cristiano
cristiano = Sales.objects.get(id=373)
print("CRISTIANO VISINHO:")
for item in cristiano.salesitems_set.all():
    total = float(item.price) * int(item.qty)
    print(f"  {int(item.qty)}x {item.product_id.name} @ R${float(item.price):.2f} = R${total:.2f}")
print(f"Grand Total: R${float(cristiano.grand_total):.2f}")
