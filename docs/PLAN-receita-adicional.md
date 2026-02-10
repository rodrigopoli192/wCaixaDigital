# PLAN: Campos VALORRECEITAADICIONAL1 e VALORRECEITAADICIONAL2

## Contexto

Os campos `VALORRECEITAADICIONAL1` e `VALORRECEITAADICIONAL2` são **campos distintos** retornados pelas rotinas SQL. Devem ser:
- **Importados** separadamente (não somados em `valor`)
- **Armazenados** em campos próprios no banco
- **Exibidos** em colunas separadas na preview e na listagem
- **Somados** na consolidação (agrupamento por protocolo + valor total)

## Alterações

---

### 1. Model — `MovimentoCaixa` e `MovimentoImportado`

#### [MODIFY] [models.py](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/caixa_nfse/caixa/models.py)

- Adicionar **2 novos campos** `DecimalField` em `MovimentoCaixa` (após `taxa_judiciaria`, linha ~418):
  - `valor_receita_adicional_1` — `_(\"Receita Adicional 1")`, max_digits=14, decimal_places=2, default=0
  - `valor_receita_adicional_2` — `_(\"Receita Adicional 2")`, max_digits=14, decimal_places=2, default=0
- Adicionar os mesmos campos em `MovimentoImportado` (após `taxa_judiciaria`, linha ~780)
- Incluir ambos em `TAXA_FIELDS` de `MovimentoCaixa` → herança automática para `MovimentoImportado`

---

### 2. Migration

- `python manage.py makemigrations caixa`

---

### 3. Importador — `importador.py`

#### [MODIFY] [importador.py](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/caixa_nfse/caixa/services/importador.py)

- **Reverter** o mapeamento errado (VALORRECEITAADICIONAL1/2 → `valor`)
- **Adicionar** ao `AUTO_MAP_ALIASES`:
  - `"VALORRECEITAADICIONAL1"` → `"valor_receita_adicional_1"`
  - `"VALORRECEITAADICIONAL2"` → `"valor_receita_adicional_2"`
- Incluir os campos em `_ACCUMULATE_FIELDS`
- Os campos já serão incluídos automaticamente no agrupamento via `TAXA_FIELDS`

---

### 4. Templates

#### [MODIFY] [importados_preview.html](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/templates/caixa/partials/importados_preview.html)

- Adicionar 2 colunas no `<thead>`: `Rec. Adic. 1` e `Rec. Adic. 2`
- Adicionar 2 `<td>` no `<tbody>` exibindo os valores

#### [MODIFY] [importados_list.html](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/templates/caixa/partials/importados_list.html)

- Adicionar as mesmas colunas (se existirem na listagem de pendentes)

---

### 5. Valor Total

- Na fórmula de `valor_total_taxas`, os novos campos já entram automaticamente por estarem em `TAXA_FIELDS`
- Na preview (grouping do `views.py`), os campos já entram via `SUMMABLE = set(TAXA_FIELDS) | {"valor", ...}`

---

## Verificação

1. Rodar migration
2. Executar rotina que retorne `VALORRECEITAADICIONAL1` e `VALORRECEITAADICIONAL2`
3. Confirmar que preview mostra colunas separadas com valores corretos
4. Importar e verificar que `MovimentoImportado` tem os valores nos campos certos
5. Rodar `python manage.py test caixa_nfse.caixa.tests.test_services_importacao`
