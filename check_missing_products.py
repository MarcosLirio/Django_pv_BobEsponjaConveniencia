#!/usr/bin/env python
"""
Script para diagnosticar comandas com produtos deletados
"""
import os
import sys
import django
from pathlib import Path

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'conveniencia_bobesponja.settings')
sys.path.insert(0, str(Path(__file__).parent))
django.setup()

from conveniencia_bobesponjaApp.models import Sales, Salesitems, Products
from decimal import Decimal

print("\n" + "="*80)
print("DIAGNÓSTICO: COMANDAS COM PRODUTOS DELETADOS/INDISPONÍVEIS")
print("="*80 + "\n")

# Buscar todas as comandas abertas
open_sales = Sales.objects.filter(status=Sales.STATUS_OPEN).order_by('date_added')

problematic_sales = []
total_missing_value = Decimal('0')

for sale in open_sales:
    items = sale.salesitems_set.all()
    missing_items = []
    missing_value = Decimal('0')
    
    for item in items:
        product = Products.objects.filter(id=item.product_id_id).first()
        
        # Verifica se produto foi deletado OU se está inativo
        if not product or not product.status:
            item_total = Decimal(str(item.price)) * Decimal(str(item.qty))
            missing_value += item_total
            
            status_msg = "DELETADO" if not product else "INATIVO"
            product_name = product.name if product else "?"
            
            missing_items.append({
                'product_id': item.product_id_id,
                'product_name': product_name,
                'qty': item.qty,
                'price': item.price,
                'total': float(item_total),
                'status': status_msg
            })
    
    if missing_items:
        problematic_sales.append({
            'sale': sale,
            'missing_items': missing_items,
            'missing_value': float(missing_value),
            'total_items': items.count(),
            'missing_count': len(missing_items)
        })
        total_missing_value += missing_value

if not problematic_sales:
    print("✅ Nenhuma comanda com produtos faltando encontrada!")
    sys.exit(0)

print(f"⚠️  ENCONTRADAS {len(problematic_sales)} COMANDA(S) COM PRODUTOS FALTANDO\n")

for idx, item in enumerate(problematic_sales, 1):
    sale = item['sale']
    print(f"\n{idx}. Comanda: {sale.comanda_code or f'(ID:{sale.id})'}")
    print(f"   Cliente: {sale.customer.name if sale.customer else 'Sem cliente'}")
    print(f"   Status: {'ABERTA' if sale.status == Sales.STATUS_OPEN else sale.status}")
    print(f"   Data Criação: {sale.date_added.strftime('%d/%m/%Y %H:%M') if sale.date_added else 'N/A'}")
    print(f"   Total Items: {item['total_items']} | Faltando: {item['missing_count']}")
    print(f"   Valor dos itens faltando: R$ {item['missing_value']:.2f}")
    print(f"   Grand Total da Comanda: R$ {float(sale.grand_total):.2f}")
    print(f"   Valor Pago: R$ {float(sale.tendered):.2f}")
    print(f"   Pendente: R$ {max(float(sale.grand_total) - float(sale.tendered), 0):.2f}")
    print(f"\n   Items Faltando:")
    for m_item in item['missing_items']:
        print(f"      - [{m_item['status']}] ID:{m_item['product_id']} | {m_item['product_name']} | Qtd:{m_item['qty']} x R${m_item['price']:.2f} = R${m_item['total']:.2f}")

print(f"\n{'='*80}")
print(f"TOTAL DE VALOR FALTANDO EM TODAS AS COMANDAS: R$ {float(total_missing_value):.2f}")
print(f"{'='*80}\n")

print("RECOMENDAÇÕES:")
print("1. Verificar se esses produtos foram deletados acidentalmente")
print("2. Reativar os produtos no sistema se encontrados")
print("3. Caso contrário, os valores já estão corretos no sistema (linha vermelha no caixa)")
print()
