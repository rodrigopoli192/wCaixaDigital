# PLAN: Destaque no nome da pessoa e badge colorido na forma de pagamento

## Problema
No card de movimento, o nome da pessoa e a forma de pagamento estão com estilo `text-slate-500` — quase invisíveis.

## Alterações

### [MODIFY] [_movimento_card.html](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/templates/caixa/partials/_movimento_card.html)

#### 1. Nome da pessoa (Apresentante/Cliente) — destaque laranja
- Ícone `person` → cor `text-primary` (laranja)
- Texto do nome → `text-white font-medium` (branco, bold)

#### 2. Forma de pagamento — badge colorido por tipo
Usar `mov.forma_pagamento.tipo` para determinar a cor do badge:

| Tipo | Cor |
|------|-----|
| DINHEIRO | emerald (verde) |
| PIX | cyan |
| DEBITO | blue (azul) |
| CREDITO | purple (roxo) |
| BOLETO | amber (amarelo) |
| TRANSFERENCIA | indigo |
| CHEQUE | slate |
| OUTROS | gray |

Template com `{% if %}` para cada tipo, estilo similar aos badges de status já existentes.

**1 arquivo, linhas 83-99.**
