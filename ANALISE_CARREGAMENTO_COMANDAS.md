# Análise: Sistema de Carregamento de Comandas (POS/Caixa)

**Data**: 26 de maio de 2026  
**Escopo**: Views de carregamento de "Comandas em Aberto" e "Lista de Clientes"

---

## 1. CARREGAMENTO DE "COMANDAS EM ABERTO" (POS)

### View: `pos()` - `/conveniencia_bobesponjaApp/views.py` linhas 1512-1575

#### Dados Retornados em `open_comandas_json`:
```
{
  'id': int,                      // ID da venda (Sales.id)
  'code': str,                    // Código da venda (Sales.code)
  'comanda_code': str,            // Identificador da comanda (nome/número)
  'customer_id': int|null,        // ID do cliente (pode ser null)
  'customer_name': str,           // Nome do cliente (vazio se sem cliente)
  'customer_phone': str,          // Telefone do cliente
  'sub_total': float,             // Subtotal (sem desconto)
  'grand_total': float,           // Total final (com desconto)
  'tendered': float,              // Montante pago/recebido
  'balance_due': float,           // Valor pendente = max(grand_total - tendered, 0)
  'item_count': int,              // Quantidade de items
  'items': [                      // Array COMPLETO de items
    {
      'product_id': int,
      'qty': int,
      'price': float
    }
  ]
}
```

#### Origem dos Dados:
| Campo | Origem | Notas |
|-------|--------|-------|
| item_count | `len(sale_items)` | Contagem direta dos items carregados |
| sub_total | `sale.sub_total` | Campo do modelo (não recalculado) |
| balance_due | `max(sale.grand_total - sale.tendered, 0)` | Calculado no backend |
| items | `sale.salesitems_set.all()` | **TODOS os items** (sem limite/filter) |

#### Filtros Aplicados:
```python
open_sales = Sales.objects.filter(status=Sales.STATUS_OPEN)
if not request.user.is_superuser:
    open_sales = open_sales.filter(user=request.user)  # ⚠️ Filtra por user
open_sales = open_sales.prefetch_related('salesitems_set__product_id')
open_sales = open_sales.order_by('-date_updated', '-id')
```

**Filtros que PODERIAM remover items:**
- ❌ NÃO há `.exclude()` em items
- ✅ Todos os `Salesitems` associados à `Sale` são inclusos

---

## 2. CARREGAMENTO NA "LISTA DE CLIENTES" (Via "Ver Comandas")

### View: `salesList()` - `/conveniencia_bobesponjaApp/views.py` linhas 1893-1960

#### Fluxo:
1. Usuário clica botão "Ver Comandas" em `customers.html` (linha 102)
2. Redireciona: `window.location.href = '/sales/?customer_id=' + customerId`
3. View `salesList()` é acionada com parâmetro `customer_id`

#### Dados Retornados em `sale_data`:
```python
data = {
  # Todos os campos do modelo Sales (via _meta.get_fields):
  'id', 'user_id', 'customer_id', 'code', 'status', 'comanda_code',
  'sub_total', 'grand_total', 'discount_type', 'discount_value', 
  'discount_amount', 'tendered', 'amount_change', 'payment_methods',
  'payment_other_detail', 'date_added', 'date_updated',
  
  # Adicionados pela view:
  'items': Salesitems.objects.filter(sale_id=sale).all(),  # ⚠️ Veja abaixo
  'item_count': len(data['items']),
  'cashier': sale.user.username,
  'payment_methods_display': sale.get_payment_methods_display(),
  'payment_other_detail': sale.payment_other_detail,
  'status_display': sale.get_status_display(),
}
```

#### Filtros Aplicados:

**Sem filtro de customer_id:**
```python
sales_queryset = Sales.objects.all() if request.user.is_superuser else Sales.objects.filter(user=request.user)
```

**COM filtro de customer_id:**
```python
# ⚠️ IGNORA O FILTRO DE USER - mostra TODAS as vendas do cliente
sales_queryset = Sales.objects.filter(customer_id=int(customer_id))
```

**Se open_comandas=true:**
```python
sales_queryset = sales_queryset.filter(status=Sales.STATUS_OPEN)
sales_queryset = sales_querquet.exclude(comanda_code__isnull=True)
sales_queryset = sales_queryset.exclude(comanda_code='')
```

**Order:** `-date_added`

#### Items na Lista de Clientes:
```python
data['items'] = Salesitems.objects.filter(sale_id=sale).all()
```

**Filtros em items:**
- ❌ NÃO há `.exclude()` em Salesitems
- ✅ Todos os items associados são carregados
- ⚠️ **QUERY INDIVIDUAL por Sale** (N+1 problem!)

---

## 3. CARREGAMENTO VIA `loadOpenComanda()` (Frontend)

### Função: `proceedLoadOpenComanda(comandaId)` - `pos.html` linhas 620-650

#### Fluxo:
1. Recebe `comandaId` (ID da Sale)
2. Busca comanda no mapa já carregado: `openComandasMap[String(comandaId)]`
3. Extrai array de items: `comanda.items` (precarregado no POS)
4. Para cada item:
   - Busca produto em `prod_arr[String(item.product_id)]`
   - Se produto não existe: adiciona a `missingProducts`
   - Se existe: chama `addProductToOrder(product, qty, price)`
5. Mostra warning se há produtos indisponíveis

#### Código:
```javascript
function proceedLoadOpenComanda(comandaId) {
    var comanda = openComandasMap[String(comandaId)]
    if (!comanda) {
        showPosMessage('Comanda nao encontrada na lista atual.', 'danger')
        return false
    }

    clearCartContents()
    $('[name="sale_id"]').val(comanda.id)
    $('[name="sale_action"]').val('checkout')
    $('[name="customer_id"]').val(comanda.customer_id || '')
    $('[name="comanda_code"]').val(comanda.comanda_code)
    
    var missingProducts = []
    comanda.items.forEach(function(item) {
        var product = prod_arr[String(item.product_id)]
        if (!product) {
            missingProducts.push(item.product_id)
            return
        }
        addProductToOrder(product, item.qty, item.price)
    })
}
```

**Potencial Problema:**
- Se um produto foi **deletado/desativado**, ele não será encontrado em `prod_arr`
- O item será ignorado silenciosamente (adicionado a `missingProducts` apenas)
- Usuário verá warning mas comanda será carregada **sem esse item**

---

## 4. DIFERENÇAS ENCONTRADAS

### Tabela Comparativa:

| Aspecto | POS (`open_comandas_json`) | Lista de Clientes (`sales.html`) |
|--------|---------------------------|----------------------------------|
| **View** | `pos()` | `salesList()` |
| **Dados items** | Precarregados no JSON | Carregados via loop (N+1 queries) |
| **Filtro items** | `.all()` sem exclude | `.all()` sem exclude |
| **Item limit** | Sem limite | Sem limite |
| **Campos inclusos** | Mínimos (id, comanda_code, items, totals) | Completos (todos os Sales fields) |
| **Filter by user** | ✅ Sempre (se não superuser) | ✅ Exceto com customer_id |
| **Filter by customer** | ❌ Não | ✅ Sim (override user filter) |
| **open_comandas filter** | ❌ Não existe | ✅ `.exclude(comanda_code__isnull=True).exclude(comanda_code='')` |
| **Order** | `-date_updated, -id` | `-date_added` |

### Filtros/Excludes que Removem Items:
```python
# Nos dados renderizados:
❌ NENHUM exclude() em Salesitems

# Filtro de comanda_code (apenas em salesList com open_comandas=true):
✅ .exclude(comanda_code__isnull=True)
✅ .exclude(comanda_code='')
# Nota: Isso remove Comandas (Sales), não items (Salesitems)
```

---

## 5. CÁLCULO DE TOTAIS

### no Modelo (models.py):
```python
class Sales:
    sub_total = models.FloatField(default=0)      # Subtotal dos items
    grand_total = models.FloatField(default=0)    # Total com desconto
    discount_value = models.FloatField(default=0) # Valor do desconto
    discount_amount = models.FloatField(default=0) # Montante do desconto
    tendered = models.FloatField(default=0)       # Montante pago
    amount_change = models.FloatField(default=0)  # Troco
```

### Cálculo em `save_pos()` (views.py linhas 1710-1820):
```python
# Subtotal: soma de (qty * price) para cada item
computed_sub_total = Decimal('0')
for item in sale_items_payload:
    total = Decimal(price) * Decimal(qty_int)
    computed_sub_total += total

# Grand Total: subtotal - desconto
if discount_type == 'PERCENT':
    discount_amount = (computed_sub_total * discount_value) / 100
else:
    discount_amount = discount_value
grand_total = computed_sub_total - discount_amount

# Balance Due (calculado no frontend do POS):
balance_due = max(grand_total - tendered, 0)
```

---

## 6. RENDERIZAÇÃO NO FRONTEND (POS)

### Função: `renderOpenComandasList()` - `pos.html` linhas 516-530

```javascript
function renderOpenComandasList() {
    var container = $('#open-comandas-list')
    var comandas = open_comandas_json.slice().sort(...)
    
    container.empty()
    $('#open-comandas-count').text(comandas.length)
    
    comandas.forEach(function(comanda) {
        var line = $('<button...></button>')
        var customerLabel = comanda.customer_name ? ' | ' + comanda.customer_name : ''
        var balanceLabel = comanda.balance_due > 0 ? ' | Pendente ' + formatBRL(comanda.balance_due) : ''
        line.html(
            '<strong>Comanda ' + comanda.comanda_code + '</strong> ' +
            '<span class="badge">ID #' + comanda.id + '</span>' +
            customerLabel +
            '<br><small>' + comanda.item_count + ' item(ns) | ' + 
            formatBRL(comanda.sub_total) + balanceLabel + '</small>'
        )
        container.append(line)
    })
}
```

**Campos Exibidos:**
- ✅ comanda_code (título)
- ✅ id (badge)
- ✅ customer_name (se disponível)
- ✅ item_count (contagem)
- ✅ sub_total (valor)
- ✅ balance_due (se > 0)

---

## 7. RESUMO EXECUTIVO

### ✅ Items Completos?
- **POS**: SIM - Todos os `Salesitems` são carregados em `open_comandas_json`
- **Lista de Clientes**: SIM - Todos os `Salesitems` são carregados via loop

### ⚠️ Filtros/Excludes?
| Contexto | Há Exclude? | Impacto |
|----------|-----------|--------|
| Items no POS | ❌ NÃO | Todos aparecem |
| Items na Lista | ❌ NÃO | Todos aparecem |
| Comandas abertas | ✅ SIM (no `salesList`) | Remove comandas sem `comanda_code` |
| Produtos no carrinho | ✅ SIM (no frontend) | Produtos deletados geram warning |

### 🔍 Diferença de Totais?
**Possíveis causas:**
1. **Order diferente**: POS ordena por `-date_updated`, Lista ordena por `-date_added`
2. **User filter**: POS mostra só do usuário, Lista (com customer_id) mostra todas
3. **sub_total storage**: É armazenado no BD, pode estar desatualizado se recalculado manual
4. **Rounding**: Cálculo de desconto pode gerar pequenas diferenças de arredondamento

---

## 8. RECOMENDAÇÕES

### Para Sincronizar Dados:
1. ✅ Usar `prefetch_related()` em `salesList` para evitar N+1 queries
2. ✅ Adicionar index em `Sales.customer_id` e `Sales.status`
3. ⚠️ Considerar cache de `open_comandas_json` (dados estáticos até nova operação)
4. ⚠️ Recalcular `sub_total/grand_total` antes de exibir se houver suspeita de inconsistência

### Para Debug:
- Comparar `sale_id` de POS vs Lista para mesma comanda
- Verificar `date_added` vs `date_updated` para ordenação
- Buscar produtos excluídos usando IDs em `missingProducts`
