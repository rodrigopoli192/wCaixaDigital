# Exibir Status "Cadastro Completo" na Listagem e Detalhe de Clientes

O campo `cadastro_completo` já existe no model `Cliente` (BooleanField, default=True). Clientes criados via importação recebem `cadastro_completo=False`. Atualmente essa informação **não é visível** em nenhuma tela. O objetivo é adicioná-la à listagem e ao detalhe.

---

## Proposed Changes

### Templates

#### [MODIFY] [cliente_list.html](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/templates/clientes/cliente_list.html)

- Adicionar coluna **"Status"** na tabela (entre "Localização" e "Ações")
- Badge visual:
  - ✅ `cadastro_completo=True` → badge verde "Completo"
  - ⚠️ `cadastro_completo=False` → badge amarelo/warning "Incompleto"
- Atualizar `colspan` da linha vazia de 6 → 7

---

#### [MODIFY] [cliente_detail.html](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/templates/clientes/cliente_detail.html)

- Adicionar badge **"Cadastro Incompleto"** no header, ao lado do badge Ativo/Inativo (linhas 16-23)
- Exibido **somente quando** `cadastro_completo=False` (warning visual para chamar atenção)
- Badge estilo warning (amarelo) com ícone `error` para destacar pendência

---

### Filtro (opcional, baixo esforço)

#### [MODIFY] [filters.py](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/caixa_nfse/clientes/filters.py)

- Adicionar filtro `cadastro_completo` como `BooleanFilter` no `ClienteFilter`

#### [MODIFY] [cliente_list.html](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/templates/clientes/cliente_list.html)

- Adicionar select de filtro "Status Cadastro" (Todos / Completo / Incompleto) nos filtros da listagem

---

## Verification Plan

### Testes Automatizados

Arquivo existente: `caixa_nfse/clientes/tests/test_views.py`

Comando: `python -m pytest caixa_nfse/clientes/tests/test_views.py -v`

Adicionar 2 testes:

1. **`test_list_shows_cadastro_completo_badge`** — Cria cliente com `cadastro_completo=False`, acessa a listagem e verifica que o texto "Incompleto" está presente no HTML.
2. **`test_detail_shows_cadastro_incompleto_badge`** — Acessa detalhe de cliente com `cadastro_completo=False` e verifica presença do badge "Cadastro Incompleto".

### Verificação Visual (Manual)

1. Acessar `/clientes/` no navegador
2. Verificar que a coluna "Status" aparece na tabela com badges verdes/amarelos
3. Clicar em um cliente com cadastro incompleto → verificar badge amarelo no header do detalhe
4. Testar filtro "Status Cadastro" selecionando "Incompleto" → apenas clientes incompletos devem aparecer
