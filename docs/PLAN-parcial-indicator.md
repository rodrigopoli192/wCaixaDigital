# Sinalização de Pagamento Parcial nas Movimentações do Caixa

## Problema

Quando um `MovimentoCaixa` é gerado a partir de uma confirmação de recebimento parcial (via `ParcelaRecebimento`), ele aparece na lista de movimentações sem nenhuma indicação visual de que faz parte de um pagamento parcial. O operador não consegue identificar rapidamente quais movimentos são parcelas, nem visualizar o histórico completo de pagamentos do protocolo.

## Solução

Sinalizar visualmente os movimentos que são parcelas de pagamento e oferecer um modal/dropdown para visualizar todos os pagamentos já realizados para aquele protocolo.

---

## Proposed Changes

### Backend — View

#### [MODIFY] [views.py](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/caixa_nfse/core/views.py)

Na `MovimentosListView`, adicionar `prefetch_related("parcela_recebimento__movimento_importado__parcelas")` ao queryset para que o template possa acessar a relação sem queries N+1.

```python
# No select_related/prefetch_related do queryset:
movimentos = MovimentoCaixa.objects.filter(...).select_related(
    "abertura__caixa", "abertura__operador", "forma_pagamento"
).prefetch_related(
    "parcela_recebimento",
    "parcela_recebimento__movimento_importado__parcelas",
    "parcela_recebimento__movimento_importado__parcelas__forma_pagamento",
    "parcela_recebimento__movimento_importado__parcelas__recebido_por",
)
```

---

### Frontend — Card de Movimento

#### [MODIFY] [_movimento_card.html](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/templates/caixa/partials/_movimento_card.html)

Adicionar badge + dropdown colapsável quando `mov.parcela_recebimento.exists` for verdadeiro (apenas para `MovimentoCaixa`, ou seja, quando `show_tipo` é `True`):

1. **Badge "Parcela X/N"** — Exibe badge amber ao lado do tipo (Entrada) indicando o número da parcela
2. **Botão "Ver Pagamentos"** — Abre um dropdown Alpine.js mostrando todas as parcelas do mesmo `MovimentoImportado`
3. **Dropdown de pagamentos** — Lista com: nº parcela, valor, forma de pagamento, data, operador

```
┌─────────────────────────────────────────────────────────┐
│ Protocolo: 12345  Descrição  [Entrada] [Parcela 2/3] 💰│
│ Forma: Dinheiro  Data: 12/02  Caixa 1   R$ 150,00      │
├─────────────────────────────────────────────────────────┤
│ 📋 Histórico de Pagamentos (3 parcelas)                 │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ #1  R$ 100,00  Dinheiro  10/02/2026  João           │ │
│ │ #2  R$ 150,00  Dinheiro  12/02/2026  Maria  ← atual │ │
│ │ #3  (pendente) R$ 50,00 restantes                   │ │
│ └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

**Lógica no template:**
```django
{% if show_tipo and mov.parcela_recebimento.exists %}
  {% with parcela=mov.parcela_recebimento.first %}
    <!-- Badge: Parcela X/N -->
    <!-- Botão toggle para ver histórico -->
    <!-- Dropdown com todas as parcelas do movimento_importado -->
  {% endwith %}
{% endif %}
```

---

## Verification Plan

### Manual
- Abrir o dashboard, verificar que movimentos parciais mostram badge "Parcela X/N"
- Clicar em "Ver Pagamentos" e verificar que o dropdown mostra todas as parcelas
- Verificar que movimentos normais (sem parcela) não mostram nenhum badge extra
- Verificar em dark mode que as cores estão consistentes
