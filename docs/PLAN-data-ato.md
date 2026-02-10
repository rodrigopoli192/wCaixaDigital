# PLAN: Importar Data do Ato (DATA_ATO)

## Contexto
A SQL retorna `DATA_ATO` (data da confecção do ato). Essa data é **independente** de `data_hora` (data do pagamento/confirmação no caixa). O ato pode ter sido praticado em um dia e pago em outro.

## Alterações

### [MODIFY] [models.py](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/caixa_nfse/caixa/models.py)
- Adicionar `data_ato = DateField(null=True, blank=True)` no `MovimentoImportado`
- Campo informativo, **não** afeta `data_hora` do `MovimentoCaixa`

### [MODIFY] [importador.py](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/caixa_nfse/caixa/services/importador.py)
- Adicionar alias `"DATA_ATO": "data_ato"` no `AUTO_MAP_ALIASES`
- Parse de data nos formatos: YYYYMMDD, DD/MM/YYYY, YYYY-MM-DD

### [MODIFY] [_movimento_card.html](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/templates/caixa/partials/_movimento_card.html)
- Exibir `data_ato` na Row 2 dos cards de pendentes (ex: "Ato: 05/02/2026")

### Migration
- `makemigrations` para o novo campo

## Verificação
- Importar dados com DATA_ATO na SQL
- Confirmar que a data aparece no card de pendentes
- `data_hora` do `MovimentoCaixa` NÃO é afetada
