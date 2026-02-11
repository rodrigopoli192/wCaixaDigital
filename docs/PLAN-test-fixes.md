# PLAN: Correção de Testes Unitários Falhando

> **56 falhas + 5 erros** distribuídos em **10 arquivos de teste** com **8 causas-raiz**

---

## Resumo do Diagnóstico

| # | Causa-Raiz | Testes Afetados | Prioridade | Arquivos a Corrigir |
|---|-----------|----------------|------------|---------------------|
| 1 | DRF Pagination ordering `created` → `created_at` | 4 | P0 | `caixa_nfse/api/views.py` ou DRF settings |
| 2 | Export views retornando `str`/`bytes` em vez de `HttpResponse` | 16 | P0 | `caixa_nfse/relatorios/views.py` ou `test_exports.py` |
| 3 | Auditoria: signals não criando logs + hash chaining + views 403 | 14 | P1 | `auditoria/tests/` (3 arquivos) |
| 4 | Caixa: campos obrigatórios faltando, lógica de movimento, HTMX 403 | 11 | P1 | `caixa/tests/test_views.py`, `test_views_extra.py`, `test_models.py` |
| 5 | Contabil: URL `contas` e `lancamento_list` inexistentes | 4 | P2 | `contabil/tests/test_views.py` ou `contabil/urls.py` |
| 6 | NFS-e: template usa `nota` em vez de `notafiscalservico` + mock path errado | 3 | P2 | `nfse/tests/test_views.py` ou `nfse/templates/` |
| 7 | Clientes: form validation retornando 200 em vez de 302/204 + tenant no model test | 3 | P2 | `clientes/tests/` |
| 8 | Backoffice: create retorna 200, delete não apaga + fixture fiscal | 2+4E | P3 | `backoffice/tests/`, `fiscal/tests/` |

---

## Fase 1 — Correções de Alta Prioridade (P0)

### 1.1 DRF Pagination Ordering (`created` → `created_at`)

**Problema:** `FieldError: Cannot resolve keyword 'created'`. O DRF `CursorPagination` usa `ordering = '-created'` por padrão, mas os models usam `created_at`.

**Arquivos afetados:**
- `caixa_nfse/api/tests/test_views.py` — 4 testes: `test_list_caixas_tenant_isolation`, `test_list_no_tenant_user`, `test_list_clientes`, `test_list_notas`

**Correção:** Verificar e corrigir o `ordering` no `DEFAULT_PAGINATION_CLASS` em settings ou definir `ordering` na pagination class da API.

**Verificação:** `python -m pytest caixa_nfse/api/tests/test_views.py -k "test_list" -v`

---

### 1.2 Export Views Retornando `str`/`bytes` (Relatórios)

**Problema:** `AttributeError: 'str' object has no attribute 'get'` — As views de export estão retornando string em vez de `HttpResponse`.

**Arquivos afetados:**
- `caixa_nfse/relatorios/tests/test_exports.py` — 14 testes (7 PDF + 7 XLSX)
- `caixa_nfse/relatorios/tests/test_views.py` — 2 testes adicionais

**Correção:** Investigar a view de export e garantir que retorna `HttpResponse` com content-type correto. Possível bug na implementação do export ou nos mocks do teste.

**Verificação:** `python -m pytest caixa_nfse/relatorios/tests/ -v`

---

## Fase 2 — Correções de Prioridade Média (P1)

### 2.1 Auditoria (14 falhas)

| Sub-grupo | Testes | Causa |
|-----------|--------|-------|
| Signals (4) | `test_signal_user_logged_in/out`, `test_signal_login_failed`, `test_decorator_audit_action_success` | Signals não criando `RegistroAuditoria` — desconectados ou lógica alterada |
| Hash Chaining (3) | `test_chaining`, `test_integridade_tenant_filter`, `test_integridade_broken` | `hash_anterior` não bate com `hash_registro` — algoritmo de hash mudou |
| Request session (1) | `test_registrar_with_request` | `WSGIRequest` sem `.session` — falta `SessionMiddleware` no mock |
| Views 403 (4) | `test_list_access`, `test_list_filters`, `test_detail_access`, `test_export_csv` | Usuário sem permissão — precisa ser `is_staff` ou ter permission específica |
| URL + Immutable (2) | `test_integrity_check_json`, `test_integrity_report_fail` | URL `auditoria:integrity` não existe + save protegido contra edição |

**Correção:** Cada sub-grupo requer abordagem diferente: ajustar setup de testes (permissões, session), verificar lógica de hash e URL patterns.

**Verificação:** `python -m pytest caixa_nfse/auditoria/tests/ -v`

---

### 2.2 Caixa (10 falhas + 1 erro)

| Sub-grupo | Testes | Causa |
|-----------|--------|-------|
| Model time-sensitive (1) | `test_is_operacional_hoje` | `is_operacional_hoje` retorna False perto de meia-noite (timezone) |
| saldo_abertura NOT NULL (2 no core) | `test_dashboard_alerts_and_totals`, `test_dashboard_operador_context_full` | `AberturaCaixa.objects.create()` sem `saldo_abertura` |
| Movimento não salva (1) | `test_movimento_success` | `abertura.movimentos.count() == 0` — form ou view mudou |
| Movimento invalid form (1) | `test_movimento_invalid_form` | Retorna 302 em vez de 200 |
| Saldo saída (1) | `test_movimento_saida_decreases_balance` | Saldo não atualiza (100→70 esperado, fica 100) |
| HTMX 403 (3) | `test_htmx_request_returns_partial`, `test_movimento_htmx_post_success`, `test_fechar_caixa_post_no_abertura` | Operador precisa permissão `is_operador` ou similar |
| Fixture missing (1E) | `test_rejeitar_fechamento_sem_justificativa` | Fixture `fechamento` não definida |
| Misc (2) | `test_block_retroactive_movement`, `test_novo_movimento_retroactive_htmx` | Status codes trocados |

**Correção:** Ajustar setup com campos obrigatórios, corrigir permissões HTMX, adicionar fixture `fechamento`, verificar lógica de saldo.

**Verificação:** `python -m pytest caixa_nfse/caixa/tests/ caixa_nfse/core/tests/test_views.py -v`

---

## Fase 3 — Correções de Prioridade Baixa (P2)

### 3.1 Contabil: URLs Inválidas (4 falhas)

**Problema:** `NoReverseMatch: Reverse for 'contas' not found` e `'lancamento_list' not found`

**Correção:** Verificar `contabil/urls.py` e ajustar os nomes nos testes ou adicionar as URLs faltantes.

**Verificação:** `python -m pytest caixa_nfse/contabil/tests/test_views.py -v`

---

### 3.2 NFS-e: Template Context + Mock Path (3 falhas)

- `test_detail_access`: Template usa `{{ nota.xxx }}` mas `DetailView` passa `notafiscalservico`
- `test_enviar_trigger_task`, `test_enviar_fail_not_rascunho`: Mock path `caixa_nfse.nfse.views.enviar_nfse` errado

**Correção:** Ajustar `context_object_name` na view ou template. Corrigir caminho do mock.

**Verificação:** `python -m pytest caixa_nfse/nfse/tests/test_views.py -v`

---

### 3.3 Clientes: Form Validation (3 falhas)

- `test_valid_documents`: `full_clean()` falha por tenant UUID inválido no setup
- `test_create_post_success`: Retorna 200 (form com erro) em vez de 302
- `test_create_post_htmx_success`: Retorna 200 em vez de 204

**Correção:** Ajustar dados de teste para incluir todos os campos obrigatórios.

**Verificação:** `python -m pytest caixa_nfse/clientes/tests/ -v`

---

## Fase 4 — Correções Menores (P3)

### 4.1 Backoffice (2 falhas)

- `test_create_tenant_flow`: 200 em vez de 302 — form com campos obrigatórios faltando
- `test_delete_tenant`: `tenant.pk` ainda existe após delete

**Verificação:** `python -m pytest caixa_nfse/backoffice/tests/ -v`

### 4.2 Fiscal (4 erros)

- Todos falham no `setup_method` por `NOT NULL: valor_servicos` ao criar `LivroFiscalServicos`

**Correção:** Adicionar `valor_servicos=Decimal("100.00")` no setup.

**Verificação:** `python -m pytest caixa_nfse/fiscal/tests/ -v`

---

## Verificação Final

```bash
# Rodar toda a suite
python -m pytest --tb=short -q

# Rodar com cobertura
python -m pytest --cov=caixa_nfse --cov-report=term-missing --tb=short
```

**Meta:** Zero falhas, zero erros, cobertura ≥ 78% (mantida ou melhorada).

---

## Ordem de Execução Recomendada

```
1. P0: API Pagination → 4 testes corrigidos
2. P0: Relatórios Exports → 16 testes corrigidos
3. P1: Auditoria → 14 testes corrigidos
4. P1: Caixa + Core Dashboard → 13 testes corrigidos
5. P2: Contabil URLs → 4 testes corrigidos
6. P2: NFS-e → 3 testes corrigidos
7. P2: Clientes → 3 testes corrigidos
8. P3: Backoffice + Fiscal → 6 testes + 4 erros corrigidos
```

**Total estimado: ~56 falhas + 5 erros → 0**
