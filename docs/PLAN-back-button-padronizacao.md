# Padronização dos Botões "Voltar" na Plataforma

Unificar todos os botões de navegação "Voltar" das páginas da plataforma (`/platform/`) para seguir o mesmo design: **botão quadrado arredondado com fundo escuro e ícone de seta laranja**.

---

## Design de Referência

- `size-10` (40×40px)
- `rounded-xl` (cantos arredondados grandes)
- Fundo: `bg-[#2B2C30]` (dark mode) / `bg-slate-800` 
- Ícone: `arrow_back` com cor `text-orange-500`
- Hover: leve brilho ou opacidade

**Classe CSS padrão proposta:**

```html
<a href="..." class="size-10 rounded-xl bg-slate-800 dark:bg-[#2B2C30] flex items-center justify-center text-orange-500 hover:bg-slate-700 dark:hover:bg-[#3a3b40] transition-colors">
    <span class="material-symbols-outlined">arrow_back</span>
</a>
```

---

## Templates Afetados (16 arquivos)

### Caixa

| # | Arquivo | Linha | Estilo Atual |
|---|---------|-------|--------------|
| 1 | `movimento_list.html` | L44 | `size-10 rounded-lg bg-slate-100 dark:bg-surface-dark border...` |
| 2 | `caixa_form.html` | L10 | `text-slate-400 hover:text-white` (bare link) |
| 3 | `importados_page.html` | L12 | `size-10 rounded-xl bg-slate-100 dark:bg-slate-700/50` |

### NFS-e

| # | Arquivo | Linha | Estilo Atual |
|---|---------|-------|--------------|
| 4 | `nfse_form.html` | L11 | `p-2 rounded-lg hover:bg-slate-100` (sem fundo) |
| 5 | `nfse_detail.html` | L12 | `p-2 rounded-lg hover:bg-slate-100` (sem fundo) |
| 6 | `nfse_dashboard.html` | L11 | `size-10 rounded-lg bg-primary/10 border border-primary/20` |
| 7 | `nfse_api_log.html` | L10 | `size-10 rounded-lg bg-primary/10 border border-primary/20` |

### Clientes

| # | Arquivo | Linha | Estilo Atual |
|---|---------|-------|--------------|
| 8 | `cliente_form.html` | L11 | Inline text link com `group-hover:-translate-x-1` |
| 9 | `cliente_detail.html` | L12 | `text-slate-400 hover:text-white` (bare link) |

### Relatórios

| # | Arquivo | Linha | Estilo Atual |
|---|---------|-------|--------------|
| 10 | `base_relatorio.html` | L11 | `size-10 rounded-lg bg-primary/10 border border-primary/20` |

### Fiscal

| # | Arquivo | Linha | Estilo Atual |
|---|---------|-------|--------------|
| 11 | `relatorio_iss.html` | L10 | Bootstrap `btn btn-outline-secondary` |

### Core

| # | Arquivo | Linha | Estilo Atual |
|---|---------|-------|--------------|
| 12 | `settings_conexao_form.html` | L14 | Text link com ícone `arrow_back` |

### Auditoria

| # | Arquivo | Linha | Estilo Atual |
|---|---------|-------|--------------|
| 13 | `auditoria_detail.html` | L150 | `border rounded-lg px-4 py-2` com texto "Voltar" |

### Backoffice

| # | Arquivo | Linha | Estilo Atual |
|---|---------|-------|--------------|
| 14 | `tenant_update.html` | L19 | `border rounded-lg px-5 py-2.5` com texto "Voltar" |
| 15 | `sistema_list.html` | L14 | Text link simples "Voltar ao Dashboard" |
| 16 | `sistema_update.html` | L14 | Text link simples "Voltar" |

> [!NOTE]
> O `403.html` tem estilo próprio standalone e **não será alterado** (não faz parte do layout `base_dark.html`).
> Botões "Cancelar" em formulários (nfse_form L192, caixa forms) também **não serão alterados** — são semanticamente diferentes.

---

## Proposed Changes

Para cada arquivo, substituir o elemento `<a>` do botão voltar pelo padrão unificado:

```html
<a href="..." class="size-10 rounded-xl bg-slate-800 dark:bg-[#2B2C30] flex items-center justify-center text-orange-500 hover:bg-slate-700 dark:hover:bg-[#3a3b40] transition-colors">
    <span class="material-symbols-outlined">arrow_back</span>
</a>
```

Casos especiais:
- **`cliente_form.html`** (L11-13): Remover o texto "Voltar para Listagem" e trocar por ícone puro
- **`auditoria_detail.html`** (L150): Remover texto "Voltar" e trocar por ícone puro
- **`tenant_update.html`** (L19-22): Remover texto "Voltar" e trocar por ícone puro
- **`sistema_list.html`** (L14-16): Remover texto "Voltar ao Dashboard" e trocar por ícone puro
- **`sistema_update.html`** (L14-16): Remover texto "Voltar" e trocar por ícone puro
- **`settings_conexao_form.html`** (L14-17): Remover texto "Voltar para Lista" e trocar por ícone puro
- **`relatorio_iss.html`** (L10-12): Trocar de Bootstrap para Tailwind; este arquivo usa `base.html` (Bootstrap), pode precisar de adaptação

---

## Verification Plan

### Visual (Browser)

1. Abrir `http://127.0.0.1:8000/platform/` e navegar pelas seguintes páginas verificando que o botão voltar tem o mesmo visual (quadrado escuro com seta laranja):
   - Dashboard → Caixas → Detalhes de caixa → Movimentações
   - NFS-e → Nova NFS-e
   - NFS-e → Detalhes de uma NFS-e
   - NFS-e → Dashboard NFS-e → Log de APIs
   - Clientes → Novo Cliente
   - Clientes → Detalhes de um Cliente
   - Relatórios (qualquer relatório)
   - Configurações → Nova Conexão
   - Auditoria → Detalhes de um registro
   - Backoffice → Editar Tenant
   - Backoffice → Sistemas → Editar Sistema

2. Verificar que o botão redireciona para a página correta ao clicar

### Manual por parte do usuário
- O usuário deverá navegar pelas páginas acima e confirmar a aparência e funcionalidade dos botões
