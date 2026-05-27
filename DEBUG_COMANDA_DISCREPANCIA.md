# 🔍 Debug: Discrepância de Valores em Comanda

## 📋 Problema Relatado
- **Lista de Comandas Abertas**: mostra R$171 (pendente)
- **Ao Abrir a Comanda**: mostra R$59
- **Diferença**: R$112 faltando

---

## 1️⃣ Campo Renderizado na Lista

**Arquivo**: [conveniencia_bobesponjaApp/templates/conveniencia/pos.html](conveniencia_bobesponjaApp/templates/conveniencia/pos.html#L548)

**Linha 548** - Função `renderOpenComandasList()`:
```javascript
line.html('<strong>Comanda ' + comanda.comanda_code + '</strong> ... <small>' + 
    comanda.item_count + ' item(ns) | ' + formatBRL(comanda.sub_total) + 
    balanceLabel + '</small>')
```

Onde:
- **`comanda.sub_total`**: valor principal exibido
- **`balanceLabel`**: `' | Pendente ' + formatBRL(comanda.balance_due)` (se `balance_due > 0`)

**Conclusão**: Se mostra "R$171 | Pendente", então:
- Sub_total pode ser X
- Balance_due é R$171

---

## 2️⃣ Fórmula de balance_due

**Arquivo**: [conveniencia_bobesponjaApp/views.py](conveniencia_bobesponjaApp/views.py#L1558)

**Linha 1558** - Função `get_open_comandas_json()`:
```python
'balance_due': max(float(sale.grand_total) - float(sale.tendered), 0)
```

**Fórmula**:
```
balance_due = max(grand_total - tendered, 0)
```

Exemplo:
- Se `grand_total = 171` e `tendered = 0` → `balance_due = 171`
- Se `grand_total = 59` e `tendered = 0` → `balance_due = 59`

---

## 3️⃣ Carregamento de Items (Frontend)

**Arquivo**: [conveniencia_bobesponjaApp/templates/conveniencia/pos.html](conveniencia_bobesponjaApp/templates/conveniencia/pos.html#L647)

**Linha 647-680** - Função `proceedLoadOpenComanda()`:

```javascript
proceedLoadOpenComanda(comandaId) {
    var comanda = openComandasMap[String(comandaId)]
    
    clearCartContents()  // ← Limpa carrinho anterior
    
    // Preenche fields da comanda
    $('[name="sale_id"]').val(comanda.id)
    $('[name="comanda_code"]').val(comanda.comanda_code)
    // ... outros fields ...
    
    // CARREGA ITEMS
    comanda.items.forEach(function(item) {
        var product = prod_arr[String(item.product_id)]
        if (!product) {
            missingProducts.push(item.product_id)
            return
        }
        addProductToOrder(product, item.qty, item.price)  // ← Adiciona cada item
    })
}
```

**Sequência**:
1. Limpa o carrinho anterior
2. Itera cada item em `comanda.items[]`
3. Chama `addProductToOrder(product, qty, price)` para cada um
4. Ao final, `calc()` recalcula o sub_total

---

## 4️⃣ Cálculo do sub_total na Renderização da Lista

**Arquivo**: [conveniencia_bobesponjaApp/views.py](conveniencia_bobesponjaApp/views.py#L1583)

**Linhas 1579-1610** - Função `get_open_comandas_json()`:

```python
for sale in open_sales:
    sale_items = []
    for item in sale.salesitems_set.all():  # ← Itera TODOS os items
        sale_items.append({
            'product_id': item.product_id_id,
            'qty': int(item.qty),
            'price': float(item.price),
        })
    open_comandas.append({
        'id': sale.id,
        'comanda_code': sale.comanda_code,
        'sub_total': float(sale.sub_total),      # ← Do banco (NOT recalculado)
        'grand_total': float(sale.grand_total),  # ← Do banco (NOT recalculado)
        'tendered': float(sale.tendered),
        'balance_due': max(float(sale.grand_total) - float(sale.tendered), 0),
        'item_count': len(sale_items),
        'items': sale_items,
    })
```

**Importante**: 
- `sub_total` e `grand_total` vêm **direto do banco** (não são recalculados)
- `balance_due` **é recalculado** localmente

---

## 5️⃣ Função `calc()` - Recalcula Totais no Carrinho

**Arquivo**: [conveniencia_bobesponjaApp/templates/conveniencia/pos.html](conveniencia_bobesponjaApp/templates/conveniencia/pos.html#L906)

```javascript
function calc() {
    var sub_total = 0
    $('#POS-field table tbody tr').each(function() {
        var price = parsePriceValue($(this).find('[name="price[]"]').val())
        var qty = parseQtyValue($(this).find('[name="qty[]"]').val())
        price = price > 0 ? price : 0
        qty = qty > 0 ? qty : 0
        var total = parseFloat(price) * parseFloat(qty)
        sub_total += parseFloat(total)
    })
    $('#grand_total').text(formatBRL(sub_total))
    $('[name="grand_total"]').val(parseFloat(sub_total))
    $('#sub_total').text(formatBRL(sub_total))
    $('[name="sub_total"]').val(parseFloat(sub_total))
}
```

**O que faz**:
1. Itera cada linha da tabela `$('#POS-field table tbody tr')`
2. Para cada linha: `sub_total += price * qty`
3. Atualiza display e campo do formulário

---

## 🔴 Possíveis Causas da Discrepância

### Causa 1: Items Duplicados no Banco ❌
- Se um item aparece 2x em `sale.salesitems_set.all()`:
  - **Na lista**: `sum(item.qty * item.price)` duplicado → mostra R$171
  - **Na tela**: `addProductToOrder()` agruparia por `product_id`, então quantity seria somada
  - **Resultado**: Valor correto no carrinho, errado na lista

### Causa 2: Items Filtrados no Frontend ❓
- Se algum item tem `status=0` ou similar:
  - **Na lista**: inclui todos os items → R$171
  - **No carrinho**: `addProductToOrder()` não consegue encontrar o produto (`prod_arr`) → pula
  - **Resultado**: Menos items no carrinho → R$59

### Causa 3: Campo `grand_total` Errado no Banco 🔴
- Se `sale.grand_total` foi salvo errado:
  - **balance_due = grand_total - tendered** usa valor errado
  - **sub_total** pode estar correto mas **grand_total** não
  
### Causa 4: Items com qty=0 ou price=0 🔴
- Se há items com `qty=0` ou `price=0`:
  - Não afetam cálculo (multiplicado por 0)
  - Mas aparecem na contagem
  - **Solução**: Filtrar `qty > 0` antes de iterar

---

## 📊 Tabela de Código-Chave

| Componente | Arquivo | Linha | Função |
|-----------|---------|-------|--------|
| **Renderização lista** | pos.html | 548 | Mostra `sub_total` + `balance_due` |
| **Balance_due calc** | views.py | 1558 | `max(grand_total - tendered, 0)` |
| **Items carregados** | pos.html | 647-680 | `proceedLoadOpenComanda()` |
| **JSON da lista** | views.py | 1573 | `get_open_comandas_json()` |
| **Totais do carrinho** | pos.html | 906 | `calc()` |
| **Sub_total no banco** | views.py | 1556 | `sale.sub_total` |
| **Grand_total no banco** | views.py | 1557 | `sale.grand_total` |

---

## 🛠️ Próximo Passo: Script de Debug

Para encontrar a comanda problemática, execute:

```bash
python scripts/debug_comanda_discrepancia.py --comanda-id <ID>
```

Este script irá:
1. Buscar a comanda pelo ID
2. Listar todos os items e valores
3. Recalcular sub_total localmente
4. Comparar com valores do banco
5. Identificar a discrepância
