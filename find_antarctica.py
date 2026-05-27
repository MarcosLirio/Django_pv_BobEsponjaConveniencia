import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','conveniencia_bobesponja.settings')
django.setup()

from conveniencia_bobesponjaApp.models import Products

# Procurar todos os produtos Antarctica
products = Products.objects.filter(name__icontains='antarctica')
print("Produtos Antarctica encontrados:")
for p in products:
    print(f"  ID: {p.id} | Nome: {p.name} | Preço: R${float(p.price):.2f}")
