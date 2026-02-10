# PLAN: Remapear VALORRECEITAADICIONAL1 → taxa_judiciaria

## Contexto
`VALORRECEITAADICIONAL1` na verdade é a `taxa_judiciaria`. Atualmente está mapeado errado para `valor_receita_adicional_1`.
`VALORRECEITAADICIONAL2` continua como `valor_receita_adicional_2`.
O campo `valor_receita_adicional_1` permanece no model mas não será preenchido.

## Alterações

### [MODIFY] [importador.py](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/caixa_nfse/caixa/services/importador.py)
- Linha 62: `"VALORRECEITAADICIONAL1": "valor_receita_adicional_1"` → `"VALORRECEITAADICIONAL1": "taxa_judiciaria"`

> [!NOTE]
> `taxa_judiciaria` já está em `_ACCUMULATE_FIELDS`, então se a SQL retornar tanto `TAXA_JUDICIARIA` quanto `VALORRECEITAADICIONAL1`, os valores serão somados corretamente.

**1 arquivo, 1 linha.**
