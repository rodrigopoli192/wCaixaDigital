# Melhorias do Backoffice — Dashboard, Busca, Logs e Health Check

Quatro melhorias para o painel do super admin (Backoffice), expandindo o dashboard com KPIs operacionais, filtros, logs de atividade e verificação de saúde das conexões externas.

---

## Proposed Changes

### 1. Dashboard de Métricas (KPIs Operacionais)

Expandir os 3 KPI cards atuais (Total Empresas, Ativas, Total Usuários) com métricas operacionais do sistema.

#### [MODIFY] [views.py](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/caixa_nfse/backoffice/views.py)

Adicionar queries no `get_context_data` do `PlatformDashboardView`:

```python
# Novos KPIs
from caixa_nfse.nfse.models import NotaFiscalServico, StatusNFSe
from caixa_nfse.caixa.models import Caixa, StatusCaixa, AberturaCaixa, MovimentoImportado
from django.utils import timezone
from datetime import timedelta

hoje = timezone.now().date()
mes_atual = hoje.replace(day=1)

context["nfse_emitidas_mes"] = NotaFiscalServico.objects.filter(
    data_emissao__gte=mes_atual, status=StatusNFSe.AUTORIZADA
).count()
context["caixas_abertos"] = Caixa.objects.filter(status=StatusCaixa.ABERTO).count()
context["movimentos_importados_mes"] = MovimentoImportado.objects.filter(
    importado_em__gte=mes_atual, confirmado=True
).count()
```

#### [MODIFY] [dashboard.html](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/templates/backoffice/dashboard.html)

Expandir o grid de KPIs de `grid-cols-3` → `grid-cols-3 lg:grid-cols-6` com 3 cards adicionais:

| Card | Ícone | Cor | Dado |
|------|-------|-----|------|
| NFS-e Emitidas (mês) | `receipt_long` | Amber | `nfse_emitidas_mes` |
| Caixas Abertos Agora | `point_of_sale` | Cyan | `caixas_abertos` |
| Movimentos Importados (mês) | `upload_file` | Indigo | `movimentos_importados_mes` |

---

### 2. Busca e Filtro de Tenants

Adicionar campo de busca inline na tabela de tenants com filtragem por nome, CNPJ e status via HTMX.

#### [MODIFY] [views.py](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/caixa_nfse/backoffice/views.py)

Adicionar filtragem no `get_queryset` do `PlatformDashboardView`:

```python
def get_queryset(self):
    qs = super().get_queryset().annotate(user_count=Count("usuarios"))
    params = self.request.GET

    if q := params.get("q"):
        qs = qs.filter(
            Q(razao_social__icontains=q)
            | Q(nome_fantasia__icontains=q)
            | Q(cnpj__icontains=q)
        )
    if status := params.get("status"):
        qs = qs.filter(ativo=(status == "ativo"))

    return qs
```

#### [MODIFY] [dashboard.html](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/templates/backoffice/dashboard.html)

Adicionar barra de busca + filtros no header da tabela (entre o título e o botão "Nova Empresa"):

```html
<!-- Inline search + status filter -->
<div class="flex items-center gap-3">
    <input type="text" name="q" placeholder="Buscar por nome ou CNPJ..."
           hx-get="{% url 'backoffice:dashboard' %}"
           hx-trigger="keyup changed delay:300ms"
           hx-target="#tenant-table-body"
           hx-select="#tenant-table-body"
           hx-push-url="true"
           class="bg-slate-50 dark:bg-background-dark border ...">
    <select name="status" hx-get="..." hx-trigger="change" ...>
        <option value="">Todos</option>
        <option value="ativo">Ativos</option>
        <option value="inativo">Inativos</option>
    </select>
</div>
```

O `<tbody>` recebe `id="tenant-table-body"` para que HTMX possa atualizar parcialmente.

---

### 3. Logs de Atividade (Últimas Ações)

Adicionar seção "Atividade Recente" no dashboard com as últimas ações registradas no sistema (`RegistroAuditoria`).

#### [MODIFY] [views.py](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/caixa_nfse/backoffice/views.py)

Adicionar no `get_context_data`:

```python
from caixa_nfse.auditoria.models import RegistroAuditoria

context["atividade_recente"] = (
    RegistroAuditoria.objects.select_related("usuario")
    .order_by("-created_at")[:15]
)
```

#### [MODIFY] [dashboard.html](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/templates/backoffice/dashboard.html)

Nova seção abaixo da tabela de tenants — card com timeline de atividades:

```html
<!-- Atividade Recente -->
<div class="bg-white dark:bg-surface-dark rounded-xl border ...">
    <h3>Atividade Recente</h3>
    <div class="divide-y ...">
        {% for log in atividade_recente %}
        <div class="flex items-center gap-3 px-6 py-3">
            <span class="material-symbols-outlined text-sm">
                <!-- Ícone baseado na ação -->
                {% if log.acao == 'CREATE' %}add_circle
                {% elif log.acao == 'UPDATE' %}edit
                {% elif log.acao == 'DELETE' %}delete
                {% elif log.acao == 'LOGIN' %}login
                {% else %}info{% endif %}
            </span>
            <div>
                <p class="text-sm font-medium">{{ log.usuario.email }} — {{ log.get_acao_display }}</p>
                <p class="text-xs text-slate-500">{{ log.tabela }} #{{ log.registro_id }} · {{ log.created_at|timesince }} atrás</p>
            </div>
        </div>
        {% endfor %}
    </div>
</div>
```

---

### 4. Health Check de Conexões Externas por Tenant

Nova view e seção no detalhe do tenant mostrando o status de cada `ConexaoExterna`, usando `SQLExecutor.get_connection()` para testar.

#### [MODIFY] [views.py](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/caixa_nfse/backoffice/views.py)

Nova view HTMX:

```python
class TenantHealthCheckView(LoginRequiredMixin, PlatformAdminRequiredMixin, View):
    """Testa todas as conexões externas de um tenant (HTMX endpoint)."""

    def post(self, request, tenant_pk):
        tenant = get_object_or_404(Tenant, pk=tenant_pk)
        conexoes = ConexaoExterna.objects.filter(tenant=tenant)
        results = []
        for c in conexoes:
            try:
                conn = SQLExecutor.get_connection(c)
                conn.close()
                results.append({"conexao": c, "ok": True, "msg": "OK"})
            except Exception as e:
                results.append({"conexao": c, "ok": False, "msg": str(e)})
        return render(request, "backoffice/partials/health_check_results.html",
                      {"results": results, "tenant": tenant})
```

#### [MODIFY] [urls.py](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/caixa_nfse/backoffice/urls.py)

```python
path("tenants/<uuid:tenant_pk>/health-check/",
     views.TenantHealthCheckView.as_view(), name="tenant_health_check"),
```

#### [NEW] [health_check_results.html](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/templates/backoffice/partials/health_check_results.html)

Partial HTMX com lista de conexões e status (badge verde/vermelho).

#### [MODIFY] [tenant_update.html](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/templates/backoffice/tenant_update.html)

Adicionar botão "🔍 Verificar Conexões" que faz POST via HTMX para `tenant_health_check`, exibindo os resultados inline.

---

## Resumo de Arquivos

| Arquivo | Ação | Mudança |
|---------|------|---------|
| `backoffice/views.py` | MODIFY | +KPIs, +filtro queryset, +activity log context, +HealthCheckView |
| `backoffice/urls.py` | MODIFY | +1 rota (health-check) |
| `templates/backoffice/dashboard.html` | MODIFY | +3 KPI cards, +busca/filtro, +seção atividade recente |
| `templates/backoffice/tenant_update.html` | MODIFY | +botão health check |
| `templates/backoffice/partials/health_check_results.html` | NEW | Partial HTMX com resultados do health check |

---

## Verification Plan

### Automated Tests
```bash
pytest caixa_nfse/backoffice/tests/ -v --tb=short
```

Novos testes a criar:
- `test_dashboard_kpis` — verifica que os 6 KPIs estão no contexto
- `test_dashboard_search_filter` — filtra por nome/CNPJ e status
- `test_dashboard_activity_log` — verifica que `atividade_recente` está presente
- `test_health_check_view` — mock do `SQLExecutor.get_connection`, testa sucesso e falha

### Manual Verification
- Acessar backoffice como superuser → confirmar 6 KPIs visíveis
- Digitar nome/CNPJ na busca → tenants filtrados via HTMX
- Seção "Atividade Recente" mostra últimas ações
- Editar tenant → "Verificar Conexões" → resultados inline
