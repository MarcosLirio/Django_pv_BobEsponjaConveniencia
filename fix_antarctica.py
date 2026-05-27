import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','conveniencia_bobesponja.settings')
django.setup()

from conveniencia_bobesponjaApp.models import Sales, Salesitems, Products

# Produtos
caixinha = Products.objects.get(id=20)  # Errado
latinha = Products.objects.get(id=34)   # Correto

print("Corrigindo items...")
print()

# JANSEN
jansen = Sales.objects.get(id=301)
print("COMANDA JANSEN:")

# Remover Caixinha errada
item_errado = Salesitems.objects.filter(sale_id=jansen, product_id_id=20).first()
if item_errado:
    print(f"  Removendo: {item_errado.qty}x {caixinha.name} @ R${float(item_errado.price):.2f}")
    item_errado.delete()

# Adicionar Latinha correta (27 unidades)
existing = Salesitems.objects.filter(sale_id=jansen, product_id_id=34).first()
if not existing:
    item = Salesitems.objects.create(
        sale_id=jansen,
        product_id_id=34,
        qty=27,
        price=latinha.price
    )
    print(f"  Adicionado: 27x {latinha.name} @ R${float(latinha.price):.2f} = R${float(latinha.price)*27:.2f}")
else:
    print(f"  Item já existe: {existing.qty}x {latinha.name}")

# Recalcular total
total = sum(float(item.price) * int(item.qty) for item in jansen.salesitems_set.all())
jansen.sub_total = total
jansen.grand_total = total
jansen.save()
print(f"  Grand Total: R${float(jansen.grand_total):.2f}")
print()

# CRISTIANO VISINHO
cristiano = Sales.objects.get(id=373)
print("COMANDA CRISTIANO VISINHO:")

# Remover Caixinha errada
item_errado = Salesitems.objects.filter(sale_id=cristiano, product_id_id=20).first()
if item_errado:
    print(f"  Removendo: {item_errado.qty}x {caixinha.name} @ R${float(item_errado.price):.2f}")
    item_errado.delete()

# Adicionar Latinha correta (3 unidades)
existing = Salesitems.objects.filter(sale_id=cristiano, product_id_id=34).first()
if not existing:
    item = Salesitems.objects.create(
        sale_id=cristiano,
        product_id_id=34,
        qty=3,
        price=latinha.price
    )
    print(f"  Adicionado: 3x {latinha.name} @ R${float(latinha.price):.2f} = R${float(latinha.price)*3:.2f}")
else:
    print(f"  Item já existe: {existing.qty}x {latinha.name}")

# Recalcular total
total = sum(float(item.price) * int(item.qty) for item in cristiano.salesitems_set.all())
cristiano.sub_total = total
cristiano.grand_total = total
cristiano.save()
print(f"  Grand Total: R${float(cristiano.grand_total):.2f}")
print()

print("✅ Corrigido! Items restaurados com produto correto (latinha/unidade)!")
