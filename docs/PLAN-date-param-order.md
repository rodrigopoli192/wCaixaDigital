# PLAN: Ordenar Data Início antes de Data Fim

## Problema
Os parâmetros de data são exibidos em ordem alfabética (`activeVars.sort()`).  
Como `DATAFIM` < `DATAINICIO` alfabeticamente, o campo "fim" aparece antes do "início", confundindo o usuário.

## Causa raiz
`importar_form.html` — linha 53:
```js
return [...vars].sort();  // alfabético → DATAFIM antes de DATAINICIO
```

## Alteração

### [MODIFY] [importar_form.html](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/templates/caixa/partials/importar_form.html)
Substituir o `.sort()` por um sort customizado que prioriza variáveis com `INICIO`/`INITIAL` antes de `FIM`/`FINAL`:

```js
return [...vars].sort((a, b) => {
    const au = a.toUpperCase();
    const bu = b.toUpperCase();
    const aIsInicio = au.includes('INICIO') || au.includes('INITIAL');
    const bIsInicio = bu.includes('INICIO') || bu.includes('INITIAL');
    if (aIsInicio && !bIsInicio) return -1;
    if (!aIsInicio && bIsInicio) return 1;
    return a.localeCompare(b);
});
```

**1 arquivo, 1 propriedade computed.**
