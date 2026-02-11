# PLAN: Exibir Receita Adicional em todas as telas

## Problema
Os campos `valor_receita_adicional_1` não aparecem na grid "Taxas Detalhadas" dos cards de movimentos (`_movimento_card.html`). 
Esta template é usada em todas as telas: pendentes, migrados, movimentos de caixa.

## Alteração

### [MODIFY] [_movimento_card.html](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/templates/caixa/partials/_movimento_card.html)

Adicionar 2 entradas na grid de taxas (após FECAD, linhas 211-213):
- `Rec. Adic. 1` → `mov.valor_receita_adicional_1`
- `Rec. Adic. 2` → `mov.valor_receita_adicional_2`

**1 template, 2 linhas adicionadas.**
