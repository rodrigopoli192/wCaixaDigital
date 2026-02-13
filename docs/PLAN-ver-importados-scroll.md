# PLAN: Ver Importados — Refresh + Scroll

## Objetivo

Ao clicar em "Ver Importados" (após importação bem-sucedida):
1. **Atualizar** somente a seção de movimentos importados (sem reload da página inteira)
2. **Scroll** suave até a seção "Movimentos Importados"

## Estado Atual

- **Botão** ([importados_results.html:20-25](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/templates/caixa/partials/importados_results.html#L20-L25)):
  ```js
  @click="window.location.reload();"
  ```
  → Faz reload completo da página. Lento e perde contexto.

- **Container** ([movimento_list.html:327-334](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/templates/caixa/movimento_list.html#L327-L334)):
  ```html
  <div id="importados-container"
       hx-get="{% url 'caixa:lista_importados' abertura.pk %}"
       hx-trigger="revealed"
       hx-swap="innerHTML">
  ```
  → Carrega via HTMX no `revealed`, mas já foi carregado. Um re-trigger atualiza os dados.

## Mudança Proposta

### [MODIFY] [importados_results.html](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/templates/caixa/partials/importados_results.html)

Substituir `window.location.reload()` por:

```diff
-@click="window.location.reload();"
+@click="
+   const el = document.getElementById('importados-container');
+   if (el) { htmx.trigger(el, 'revealed'); }
+   setTimeout(() => { if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' }); }, 300);
+"
```

**Lógica:**
1. `htmx.trigger(el, 'revealed')` → re-dispara o trigger HTMX, fazendo um GET fresco dos dados
2. `setTimeout` de 300ms → espera o HTMX completar a request antes de fazer scroll
3. `scrollIntoView({ behavior: 'smooth' })` → scroll suave até o container

## Verificação

- Após importar, clicar em "Ver Importados"
- A seção deve atualizar sem reload da página
- A tela deve rolar até a seção de movimentos importados
