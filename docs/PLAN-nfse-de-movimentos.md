# PLAN: Gerar NFS-e a partir de Movimentos Confirmados

## Contexto

O operador precisa gerar NFS-e individualmente a partir de movimentos de caixa do tipo **ENTRADA** já confirmados.
A infraestrutura backend já existe (`criar_nfse_de_movimento` em `services.py`, `emitir_nfse_movimento` em `tasks.py`).
O que falta é a **camada de UI/UX** para disparar a geração e tratar edge cases (sem cliente, já gerada).

## Decisões do Usuário

| Pergunta | Resposta |
|----------|----------|
| Gatilho | Individual (botão por movimento). Lote/automático no futuro |
| Tipos que geram NFS-e | Somente `ENTRADA` |
| Cliente obrigatório | Sim. Tela de associação se ausente |
| ServicoMunicipal | Usa padrão pré-cadastrado |
| Fluxo | Gera como **RASCUNHO** → operador revisa → envia |

---

## Proposed Changes

### Componente 1: Botão "Gerar NFS-e" no Card de Movimento

#### [MODIFY] [_movimento_card.html](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/templates/caixa/partials/_movimento_card.html)

Adicionar botão "Gerar NFS-e" ao lado do botão "Imprimir Recibo" (L206-213), **apenas para**:
- `model_type == 'movimento'` (movimentos confirmados)
- `mov.tipo == 'ENTRADA'`
- `mov.nota_fiscal` é null (ainda não gerou)

```html
{% if model_type == 'movimento' and mov.tipo == 'ENTRADA' and not mov.nota_fiscal %}
<button hx-post="{% url 'nfse:gerar_de_movimento' pk=mov.pk %}"
        hx-confirm="Gerar NFS-e para este movimento?"
        hx-target="#toast-area"
        hx-swap="innerHTML"
        class="shrink-0 p-1.5 rounded-lg hover:bg-blue-500/10 ..."
        title="Gerar NFS-e">
    <span class="material-symbols-outlined ...">receipt</span>
</button>
{% elif model_type == 'movimento' and mov.nota_fiscal %}
<a href="{% url 'nfse:detail' pk=mov.nota_fiscal.pk %}"
   class="shrink-0 p-1.5 rounded-lg ..."
   title="Ver NFS-e vinculada">
    <span class="material-symbols-outlined ...">description</span>
</a>
{% endif %}
```

**Lógica:**
1. Se não tem nota → botão azul "Gerar NFS-e" (POST HTMX)
2. Se já tem nota → link para ver a NFS-e existente (ícone `description`)

---

### Componente 2: View HTMX para Gerar NFS-e

#### [MODIFY] [views.py](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/caixa_nfse/nfse/views.py)

Nova view `GerarNFSeDeMovimentoView`:

```python
class GerarNFSeDeMovimentoView(LoginRequiredMixin, TenantMixin, View):
    """POST: gera NFS-e rascunho a partir de um MovimentoCaixa."""
    
    def post(self, request, pk):
        movimento = get_object_or_404(MovimentoCaixa, pk=pk, tenant=request.tenant)
        
        # Guards
        if movimento.tipo != TipoMovimento.ENTRADA:
            return toast_error("Somente movimentos de entrada geram NFS-e")
        if movimento.nota_fiscal_id:
            return toast_info("Este movimento já possui NFS-e vinculada")
        if not movimento.cliente_id:
            return redirect_associar_cliente(movimento)
        
        nota = criar_nfse_de_movimento(movimento)
        return redirect(nota.get_absolute_url())  # redireciona ao rascunho
```

#### [MODIFY] [urls.py](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/caixa_nfse/nfse/urls.py)

Nova rota:
```python
path("gerar/<uuid:pk>/", views.GerarNFSeDeMovimentoView.as_view(), name="gerar_de_movimento"),
```

---

### Componente 3: Modal de Associação de Cliente (quando ausente)

#### [NEW] [_associar_cliente_modal.html](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/templates/nfse/partials/_associar_cliente_modal.html)

Modal HTMX que abre quando o movimento não tem cliente:
- Select com busca (autocomplete) de clientes cadastrados
- Campo `cliente_nome` pré-preenchido como hint
- Botão "Associar e Gerar NFS-e"

#### [MODIFY] [views.py](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/caixa_nfse/nfse/views.py)

Nova view `AssociarClienteView`:
- **GET**: renderiza o modal com select de clientes
- **POST**: associa o cliente ao movimento e redireciona para `GerarNFSeDeMovimentoView`

#### [MODIFY] [urls.py](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/caixa_nfse/nfse/urls.py)

```python
path("associar-cliente/<uuid:pk>/", views.AssociarClienteView.as_view(), name="associar_cliente"),
```

---

### Componente 4: Badge NFS-e no Card (feedback visual)

#### [MODIFY] [_movimento_card.html](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/templates/caixa/partials/_movimento_card.html)

Adicionar badge visual na Row 1 do card quando `mov.nota_fiscal` existe:

```html
{% if mov.nota_fiscal %}
<span class="text-[10px] px-2 py-0.5 rounded-full font-bold shrink-0
    {% if mov.nota_fiscal.status == 'AUTORIZADA' %}bg-emerald-500/20 text-emerald-600
    {% elif mov.nota_fiscal.status == 'RASCUNHO' %}bg-amber-500/20 text-amber-600
    {% elif mov.nota_fiscal.status == 'REJEITADA' %}bg-red-500/20 text-red-600
    {% endif %}">
    NFS-e {{ mov.nota_fiscal.get_status_display }}
</span>
{% endif %}
```

---

### Componente 5: Otimização de Queries

#### [MODIFY] [views.py](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/caixa_nfse/caixa/views.py)

Na view de lista de movimentos, adicionar `select_related("nota_fiscal")` ao queryset para evitar N+1 queries ao renderizar os badges.

---

## Task Breakdown

| # | Tarefa | Prioridade | Complexidade |
|---|--------|-----------|-------------|
| 1 | Botão "Gerar NFS-e" no card | Alta | Baixa |
| 2 | `GerarNFSeDeMovimentoView` + URL | Alta | Média |
| 3 | Badge NFS-e no card | Média | Baixa |
| 4 | Modal "Associar Cliente" | Média | Média |
| 5 | `AssociarClienteView` + URL | Média | Média |
| 6 | `select_related('nota_fiscal')` na lista | Baixa | Baixa |
| 7 | Testes unitários | Alta | Média |

---

## Verification Plan

### Automated Tests
- Testar `GerarNFSeDeMovimentoView` com movimento válido (ENTRADA + cliente)
- Testar guards: tipo SAIDA, nota já existente, sem cliente
- Testar `AssociarClienteView` GET/POST

### Manual Verification
- Clicar "Gerar NFS-e" em movimento de ENTRADA com cliente → deve redirecionar para rascunho
- Clicar "Gerar NFS-e" em movimento sem cliente → deve abrir modal de associação
- Verificar que badge "NFS-e Rascunho" aparece no card após geração
- Verificar que botão não aparece para tipo SAIDA/SANGRIA
