# PLAN: Ordenar Movimentos Pendentes por Sessão e Data

## Objetivo

Na visualização de "Movimentos Importados (Aguardando Confirmação)", exibir:
1. **Primeiro**: itens da sessão atual
2. **Depois**: itens de sessões anteriores
3. **Sempre**: ordenados por `importado_em` decrescente (importados mais recentes primeiro)

## Estado Atual

- **View**: `ListaImportadosView` ([views.py:954-1014](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/caixa_nfse/caixa/views.py#L954-L1014))
  - Queryset sem `order_by` explícito → usa ordering padrão do model (indefinido para MovimentoImportado)
  - Separa `pendentes_anteriores` vs `importados_sessao_atual` via list comprehension (L1002-1004)
  - As listas Python não são re-ordenadas após o split

- **Template**: [importados_list.html](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/templates/caixa/partials/importados_list.html#L177-L205)
  - L177-189: Exibe "Sessões Anteriores" **primeiro**
  - L191-205: Exibe "Desta Sessão" **depois**

## Mudanças Propostas

---

### [MODIFY] [views.py](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/caixa_nfse/caixa/views.py)

**Queryset** (L971-980): Adicionar `.order_by("-importado_em")`

```diff
 return (
     MovimentoImportado.objects.filter(
         abertura_id=self.kwargs["pk"],
         tenant=self.request.user.tenant,
     )
     .exclude(status_recebimento=StatusRecebimento.QUITADO)
     .select_related("rotina", "conexao")
     .prefetch_related("parcelas", "parcelas__forma_pagamento", "parcelas__recebido_por")
     .annotate(itens_count=Count("itens"))
+    .order_by("-importado_em")
 )
```

> As list comprehensions em L1002-1004 já preservam a ordem do queryset, então ambas as sub-listas (anteriores e sessão atual) ficarão ordenadas por `-importado_em` automaticamente.

---

### [MODIFY] [importados_list.html](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/templates/caixa/partials/importados_list.html)

**Inverter a ordem das seções** (L177-205): Mover "Desta Sessão" para antes de "Sessões Anteriores".

```diff
         <div x-show="expanded" x-collapse class="px-4 pb-4 space-y-3">

-            <!-- Pendentes de Sessões Anteriores -->
-            {% if pendentes_anteriores %}
-            <div class="space-y-2">
-                ...Sessões Anteriores...
-            </div>
-            {% endif %}
-
             <!-- Importados Desta Sessão -->
             {% if importados_sessao_atual %}
             <div class="space-y-2">
                 ...Desta Sessão...
             </div>
             {% endif %}

+            <!-- Pendentes de Sessões Anteriores -->
+            {% if pendentes_anteriores %}
+            <div class="space-y-2">
+                ...Sessões Anteriores...
+            </div>
+            {% endif %}
+
             <!-- Fallback -->
```

> **Nota**: O label "Desta Sessão" deve aparecer **sempre** (não apenas quando há também `pendentes_anteriores`), para clarificar a separação.

---

## Verificação

- Verificar visualmente no browser que a seção "Desta Sessão" aparece acima de "Sessões Anteriores"
- Verificar que dentro de cada seção, o item mais recente aparece primeiro
- Verificar que o select-all e confirmação continuam funcionando corretamente
