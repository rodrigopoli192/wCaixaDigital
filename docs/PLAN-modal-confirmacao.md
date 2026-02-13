# PLAN: Modal de Confirmação de Pagamento

## Contexto

Atualmente a confirmação de importados usa uma **action bar inline** com selects + botão direto no template. O usuário quer um **modal dedicado** que abre ao clicar "Confirmar", com campos de pagamento, resumo de valores e validações.

## Regras de Negócio

| Regra | Descrição |
|-------|-----------|
| **Seleção múltipla** | Pode selecionar N itens e confirmar todos de uma vez |
| **Parcial só unitário** | Se selecionou >1 item, NÃO permite pagamento parcial (valor é fixo = saldo total) |
| **Parcial unitário** | Se selecionou 1 item, campo "Valor a receber" é editável para pagamento parcial |
| **Validação valor** | Valor a receber deve ser > 0 e ≤ saldo pendente |
| **Campos obrigatórios** | Forma de pagamento (select) e Tipo (Entrada/Saída) |
| **Resumo financeiro** | Exibir: valor total, já recebido, recebendo agora, saldo restante |
| **Funciona em ambos cards** | Mesmo modal para "Aguardando Saldo Restante" e "Movimentos Importados" |

## Fluxo UX

```
Seleciona itens (checkbox) → Clica "Confirmar"
    │
    ├── Se 0 selecionados → Botão desabilitado
    │
    ├── Se 1 selecionado → Modal com campo de valor EDITÁVEL
    │   └── Se valor < saldo → Aviso "Recebimento Parcial" inline
    │   └── Se valor = saldo → Confirmação simples
    │
    └── Se N selecionados → Modal com valor FIXO (soma dos saldos)
        └── Campo valor readonly, sem opção parcial
```

## Mudanças Propostas

### Frontend — `importados_list.html`

**Remover:**
- Action bar inline (selects de forma de pagamento e tipo dentro da barra)
- Modal de confirmação parcial antigo (`showModalParcial`)

**Adicionar — Modal de Confirmação:**

```
┌─────────────────────────────────────────┐
│ ✅ Confirmar Recebimento                │
├─────────────────────────────────────────┤
│                                         │
│ 📋 Itens Selecionados (N)              │
│ ┌─────────────────────────────────────┐ │
│ │ Proto 12402.00 — Balcão ...   R$19  │ │
│ │ Proto 11676.00 — Registro...  R$20  │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ Forma de Pagamento: [Dinheiro     ▼]   │
│ Tipo:               [Entrada      ▼]   │
│                                         │
│ ┌─ Resumo ──────────────────────────┐  │
│ │ Valor Total:          R$ 133,00   │  │
│ │ Já Recebido:          R$  20,00   │  │
│ │ ─────────────────────────────     │  │
│ │ Valor a Receber: [___113,00___]   │  │
│ │ Saldo Restante:       R$   0,00   │  │
│ └───────────────────────────────────┘  │
│                                         │
│ ⚠ Aviso parcial (se valor < saldo)    │
│                                         │
│         [Cancelar]  [✅ Confirmar]      │
└─────────────────────────────────────────┘
```

**Lógica Alpine.js:**

| Função | Comportamento |
|--------|---------------|
| `openModal()` | Coleta dados dos cards selecionados, calcula totais, abre modal |
| `isMultiple` | `selected.length > 1` — se true, valor readonly |
| `valorReceber` | Editável (1 item), readonly (N itens) |
| `saldoRestante` | Computed: `totalSaldo - valorReceber` |
| `canSubmit` | `valorReceber > 0 && valorReceber <= totalSaldo && formaPagamento != ''` |
| `submit()` | Monta hidden inputs + requestSubmit no form HTMX |

### Backend — `views.py`

> **Sem mudanças.** A `ConfirmarImportadosView` já recebe `importado_ids`, `forma_pagamento_id`, `tipo` e `valor_parcela_{id}` via POST. O modal apenas reorganiza o frontend que envia os mesmos dados.

### Card — `_movimento_card.html`

> **Sem mudanças.** Os `data-*` attributes (`data-imp-id`, `data-saldo`, `data-valor-total`, `data-recebido`, `data-protocolo`, `data-descricao`) já existem.

## Resumo de Arquivos

| Arquivo | Ação | Escopo |
|---------|------|--------|
| `importados_list.html` | MODIFY | Remover action bar inline, adicionar modal + nova lógica Alpine |
| `views.py` | — | Nenhuma mudança |
| `_movimento_card.html` | — | Nenhuma mudança |
| `urls.py` | — | Nenhuma mudança |

## Validações no Modal

| Validação | Momento | Feedback |
|-----------|---------|----------|
| Forma de pagamento vazia | Submit | Borda vermelha no select + mensagem |
| Valor ≤ 0 | Digitação | Botão desabilitado |
| Valor > saldo | Digitação | Input vermelho + texto "Excede o saldo" |
| Múltiplos + parcial | Abertura | Campo valor readonly + tooltip explicativo |

## Verificação

1. Selecionar 1 item → modal com valor editável → confirmar parcial → verificar saldo restante
2. Selecionar N itens → modal com valor fixo → confirmar integral → verificar HX-Refresh
3. Sem seleção → botão "Confirmar" não aparece
4. Campos obrigatórios vazios → validação impede submit
5. Funciona igual nos 2 cards (parciais e importados)
