#!/usr/bin/env python
"""
Script para debugar discrepâncias de valores em comandas.

Uso:
    python scripts/debug_comanda_discrepancia.py <COMANDA_ID>
    
Exemplo:
    python scripts/debug_comanda_discrepancia.py 42
"""

import os
import sys
import django
from decimal import Decimal

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'conveniencia_bobesponja.settings')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from conveniencia_bobesponjaApp.models import Sales, Salesitems, Products

def debug_comanda(comanda_id):
    """Debug uma comanda específica"""
    print(f"\n{'='*80}")
    print(f"🔍 DEBUGANDO COMANDA ID: {comanda_id}")
    print(f"{'='*80}\n")
    
    try:
        sale = Sales.objects.select_related('customer').prefetch_related('salesitems_set__product_id').get(id=comanda_id)
    except Sales.DoesNotExist:
        print(f"❌ ERRO: Comanda {comanda_id} não encontrada!")
        return
    
    print(f"📌 INFORMAÇÕES DA COMANDA")
    print(f"  ID: {sale.id}")
    print(f"  Código: {sale.comanda_code}")
    print(f"  Status: {sale.status}")
    print(f"  Usuário: {sale.user.username if sale.user else 'N/A'}")
    print(f"  Cliente: {sale.customer.name if sale.customer else 'N/A'}")
    print(f"  Data Criação: {sale.date_added}")
    print(f"  Data Última Atualização: {sale.date_updated}")
    
    print(f"\n💰 VALORES SALVOS NO BANCO")
    print(f"  Sub Total: R$ {sale.sub_total:.2f}")
    print(f"  Grand Total: R$ {sale.grand_total:.2f}")
    print(f"  Desconto: {sale.discount_type} = {sale.discount_value}")
    print(f"  Tendered: R$ {sale.tendered:.2f}")
    print(f"  Balance Due: R$ {max(float(sale.grand_total) - float(sale.tendered), 0):.2f}")
    print(f"  Amount Change: R$ {sale.amount_change:.2f}")
    print(f"  Formas de Pagamento: {sale.payment_methods}")
    
    # Carrega items
    items = sale.salesitems_set.all()
    print(f"\n📦 ITEMS DA COMANDA ({len(items)} item(ns))")
    print(f"{'─'*80}")
    
    if len(items) == 0:
        print("  ⚠️  AVISO: Nenhum item encontrado!")
    else:
        calculated_sub_total = Decimal('0')
        
        for idx, item in enumerate(items, 1):
            product = item.product_id
            total_item = Decimal(str(item.price)) * Decimal(str(item.qty))
            calculated_sub_total += total_item
            
            print(f"  [{idx}] {product.name}")
            print(f"      Código: {product.code} | ID: {product.id}")
            print(f"      Qty: {item.qty} × R$ {item.price:.2f} = R$ {float(total_item):.2f}")
            print(f"      Total Salvo: R$ {item.total_price:.2f}")
            
            if abs(float(total_item) - item.total_price) > 0.01:
                print(f"      ⚠️  INCONSISTÊNCIA: qty*price ({float(total_item):.2f}) ≠ total_price ({item.total_price:.2f})")
            print()
        
        print(f"{'─'*80}")
        print(f"✅ CÁLCULO LOCAL (RECALCULADO)")
        print(f"  Sub Total Recalculado: R$ {float(calculated_sub_total):.2f}")
        print(f"  Sub Total no Banco: R$ {sale.sub_total:.2f}")
        
        if abs(float(calculated_sub_total) - float(sale.sub_total)) > 0.01:
            diferenca = float(sale.sub_total) - float(calculated_sub_total)
            print(f"  ❌ DISCREPÂNCIA: R$ {diferenca:.2f} FALTANDO/SOBRANDO!")
            print(f"     → Items somam R$ {float(calculated_sub_total):.2f}")
            print(f"     → Banco registra R$ {sale.sub_total:.2f}")
        else:
            print(f"  ✅ CORRETO: Sub total bate!")
    
    # Verifica desconto
    print(f"\n🏷️  DESCONTO")
    if sale.discount_value > 0:
        if sale.discount_type == 'PERCENT':
            discount_amount = (Decimal(str(sale.sub_total)) * Decimal(str(sale.discount_value))) / Decimal('100')
        else:
            discount_amount = Decimal(str(sale.discount_value))
        
        print(f"  Tipo: {sale.discount_type}")
        print(f"  Valor: {sale.discount_value}")
        print(f"  Desconto Amount: R$ {float(discount_amount):.2f}")
        print(f"  Sub Total - Desconto = {sale.sub_total:.2f} - {float(discount_amount):.2f} = {sale.sub_total - float(discount_amount):.2f}")
        print(f"  Grand Total no Banco: R$ {sale.grand_total:.2f}")
    else:
        print(f"  Nenhum desconto aplicado")
    
    # Resumo final
    print(f"\n{'='*80}")
    print(f"📊 RESUMO")
    print(f"{'='*80}")
    
    balance_due = max(float(sale.grand_total) - float(sale.tendered), 0)
    
    print(f"  Grand Total: R$ {sale.grand_total:.2f}")
    print(f"  Tendered: R$ {sale.tendered:.2f}")
    print(f"  Balance Due: R$ {balance_due:.2f}")
    
    if len(items) > 0:
        items_total = float(calculated_sub_total)
        print(f"\n  Items Total: R$ {items_total:.2f}")
        print(f"  Sub Total (Banco): R$ {sale.sub_total:.2f}")
        
        if abs(items_total - float(sale.sub_total)) > 0.01:
            print(f"\n  ❌ PROBLEMA IDENTIFICADO!")
            print(f"     Sub Total no banco ({sale.sub_total:.2f}) não corresponde")
            print(f"     à soma dos items ({items_total:.2f})")
            
            if items_total < float(sale.sub_total):
                print(f"     → Items faltando ou com qty reduzida")
            else:
                print(f"     → Items duplicados ou qty incorreta")
    
    print(f"\n{'='*80}\n")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Uso: python scripts/debug_comanda_discrepancia.py <COMANDA_ID>")
        print("\nExemplo:")
        print("  python scripts/debug_comanda_discrepancia.py 42")
        sys.exit(1)
    
    try:
        comanda_id = int(sys.argv[1])
        debug_comanda(comanda_id)
    except ValueError:
        print(f"❌ ERRO: '{sys.argv[1]}' não é um número válido!")
        sys.exit(1)
