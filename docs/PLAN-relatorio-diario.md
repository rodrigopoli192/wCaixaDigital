# PLAN: Relatório Diário de Caixas

## Objetivo

Relatório agrupado por **Dia → Caixa** mostrando totais, quantidades, entradas/saídas, operador e breakdown por forma de pagamento. Default: últimos 7 dias.

---

## Estrutura Visual

```
┌─────────────────────────────────────────────────────┐
│  [Filtros: Data Início | Data Fim | Caixa | Filtrar]│
├─────────────────────────────────────────────────────┤
│  KPI: Total Entradas  |  Total Saídas  |  Saldo     │
├─────────────────────────────────────────────────────┤
│                                                      │
│  📅 13/02/2026                                       │
│  ┌──────────────────────────────────────────────────┐│
│  │ Caixa 3 │ Operador: João │ 3 movs               ││
│  │ Entradas: R$ 4.852  Saídas: R$ 0                ││
│  │ ├ Dinheiro: R$ 4.847  │ Débito: R$ 4,77         ││
│  └──────────────────────────────────────────────────┘│
│  ┌──────────────────────────────────────────────────┐│
│  │ Caixa 1 │ Operador: João │ 1 mov                ││
│  │ Entradas: R$ 100  Saídas: R$ 0                  ││
│  │ ├ Crédito: R$ 100                               ││
│  └──────────────────────────────────────────────────┘│
│                                                      │
│  📅 12/02/2026                                       │
│  ┌──────────────────────────────────────────────────┐│
│  │ Caixa 1 │ Operador: João │ 2 movs               ││
│  │ ...                                             ││
│  └──────────────────────────────────────────────────┘│
│  ┌─ TOTAL DO DIA ───────────────────────────────────┐│
│  │ Entradas: R$ 115  Saídas: R$ 50  Saldo: R$ 65   ││
│  └──────────────────────────────────────────────────┘│
│                                                      │
│  [Footer: Totais do período]                         │
└─────────────────────────────────────────────────────┘
```

---

## Arquivos

### [NEW] `templates/relatorios/financeiros/relatorio_diario.html`

Template com:
- Filtros (data_inicio, data_fim, caixa)
- KPIs (total_entradas, total_saidas, saldo_liquido, total_dias)
- Cards agrupados por dia → caixa com:
  - Operador responsável
  - Quantidade de movimentos
  - Entradas / Saídas / Saldo
  - Mini-tabela por forma de pagamento
- **Total do dia**: barra de resumo após os cards de cada dia com soma de entradas, saídas e saldo

### [MODIFY] `caixa_nfse/relatorios/views.py`

Nova view `RelatorioDiarioView(ExportMixin, GerenteRequiredMixin, TemplateView)`:

```python
def get_dados_diarios(self):
    # Default: últimos 7 dias
    # Query com TruncDate + annotate agrupando por dia, caixa
    # Sub-query por forma de pagamento
    # Retorna: { '2026-02-13': [ {caixa, operador, qtd, entradas, saidas, formas: [...]} ] }
```

### [MODIFY] `caixa_nfse/relatorios/urls.py`

```python
path("relatorio-diario/", views.RelatorioDiarioView.as_view(), name="relatorio_diario"),
```

### [MODIFY] `templates/relatorios/index.html`

Adicionar card na seção Financeiros com ícone `calendar_month`.

---

## Verificação

- [ ] Relatório abre com últimos 7 dias por default
- [ ] Dados agrupados por dia → caixa corretamente
- [ ] Cada card mostra operador, qtd, entradas, saídas, formas de pagamento
- [ ] Filtros de data e caixa funcionam
- [ ] Exportação PDF/XLSX funciona
- [ ] KPIs no topo conferem com soma dos cards
