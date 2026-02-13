# Debug: Relatório de Movimentações

## 🔍 Investigação

### Dados do DB vs Relatório

| Métrica | Banco | Relatório | ✅/❌ |
|---------|-------|-----------|-------|
| Total Entradas | R$ 21.920,23 | R$ 21.920,23 | ✅ Match |
| Total Saídas | R$ 83,00 | R$ 83,00 | ✅ Match |
| Total Registros | 29 | 29 | ✅ Match |

> Os cálculos das queries estão **corretos**. Os problemas são de **apresentação**.

---

## 🐛 Bugs Encontrados

### Bug 1: Footer com colunas trocadas

No `tfoot` da tabela (L108-114):

```html
<tr class="font-bold">
    <td colspan="5">Total</td>
    <td>+R$ entradas</td>   <!-- Coluna 6 = Data/Hora ❌ -->
    <td>-R$ saidas</td>     <!-- Coluna 7 = Valor ❌ -->
</tr>
```

O footer tem 7 colunas na tabela, mas o `colspan="5"` + 2 cells = 7. O total de **entradas** fica na coluna de **Data/Hora** e o total de **saídas** fica na coluna de **Valor**. Deveria ser: `colspan="6"` + 1 cell com saldo líquido, ou reestruturar para mostrar entradas e saídas corretamente.

**Fix:** Mudar `colspan="5"` para `colspan="6"` e unificar o total na coluna de Valor.

---

### Bug 2: Tabela mostra 100 mas totais contam TODOS

- `movimentos[:100]` → Apenas 100 linhas mostradas (L182)
- `totais = movimentos.aggregate(...)` → Calcula sobre **todos** (L170-174)

Com 29 movimentos hoje não há problema. Mas quando houver >100, o total nos cards será diferente da soma visual das linhas.

**Fix:** Adicionar aviso "Exibindo X de Y registros" ou paginar.

---

### Bug 3: Movimento com valor R$ 0,00

Um movimento de 09/02 tem `valor=0.00` e `descricao="11661.00"` — o valor foi salvo no campo errado. Isso é um **bug de dados**, não do relatório.

---

## Proposta de Fix

### [MODIFY] movimentacoes.html

1. **Footer**: Corrigir colspan e mostrar saldo líquido (Entradas - Saídas)
2. **Aviso de paginação**: Adicionar indicador quando exibindo parcial

### [MODIFY] views.py

1. Adicionar `total_registros_exibidos` ao contexto para o aviso

---

## Verificação

- Footer alinhado corretamente com colunas da tabela
- Soma visual das linhas = total do footer
- Aviso claro quando há mais registros que os exibidos
