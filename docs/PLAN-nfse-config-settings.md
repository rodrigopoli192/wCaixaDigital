# Mover Configuração NFS-e para Configurações do Sistema

## Contexto

A configuração NFS-e está em uma página standalone (`/nfse/config/`). O usuário quer integrá-la na página de Configurações do Sistema (`/settings/`), que já usa **HTMX tabs com partials** e tem um placeholder "NFS-e (Em Breve)".

## Proposed Changes

### 1. Template: Partial NFS-e para Settings

#### [NEW] [settings_nfse.html](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/templates/core/partials/settings_nfse.html)

Criar partial seguindo o padrão das outras tabs (`p-6`, header, conteúdo). Conteúdo reutilizado do `nfse_config.html` existente:
- Backend de emissão (select)
- Ambiente (toggle homologação/produção)
- Gerar NFS-e ao confirmar (checkbox)  
- Credenciais API (token/secret)
- Certificado digital (status)
- Botão "Testar Conexão" (HTMX)
- Botão "Salvar"

O form faz `POST` via HTMX para a mesma rota, retornando o partial atualizado com toast.

---

### 2. Rota: Endpoint settings NFS-e

#### [MODIFY] [urls.py](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/caixa_nfse/core/urls.py)

Adicionar:
```python
path("settings/nfse/", views.SettingsNFSeView.as_view(), name="settings_nfse"),
```

---

### 3. View: SettingsNFSeView  

#### [MODIFY] [views.py](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/caixa_nfse/core/views.py)

Nova view `SettingsNFSeView`:
- Herda `LoginRequiredMixin, TenantAdminRequiredMixin`
- `GET`: retorna partial `settings_nfse.html` com form `NFSeConfigForm`
- `POST`: salva config, retorna partial com toast success/error  
- Usa `get_or_create` por tenant (mesmo padrão do `NFSeConfigView` atual)

---

### 4. Template: Ativar tab NFS-e no settings.html

#### [MODIFY] [settings.html](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/templates/core/settings.html)

Substituir placeholder "NFS-e (Em Breve)" (L64-67) por botão HTMX ativo:
```html
<button 
    @click="activeTab = 'nfse'"
    hx-get="{% url 'core:settings_nfse' %}" 
    hx-target="#settings-content" 
    hx-swap="innerHTML"
    :class="activeTab === 'nfse' ? '...' : '...'"
    class="flex items-center gap-3 px-4 py-3 rounded-lg transition-all text-left">
    <span class="material-symbols-outlined">receipt_long</span>
    <span class="font-medium">NFS-e</span>
</button>
```

---

### 5. Cleanup: Remover rota standalone

#### [MODIFY] [urls.py (nfse)](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/caixa_nfse/nfse/urls.py)

- **Remover** rota `path("config/", ...)`
- **Manter** rota `path("config/testar/", ...)` (HTMX endpoint usado pelo partial)

#### [MODIFY] [nfse_list.html](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/templates/nfse/nfse_list.html)

- Botão "Configurações" → redirecionar de `nfse:config` para `core:settings` com `?tab=nfse`

#### [DELETE] [nfse_config.html](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/templates/nfse/nfse_config.html)

Não será mais necessário — substituído pelo partial.

#### [MODIFY] [views.py (nfse)](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/caixa_nfse/nfse/views.py)

- **Remover** `NFSeConfigView` (movida para core)
- **Manter** `NFSeTestarConexaoView` (HTMX endpoint independente)

---

### 6. Testes

#### [MODIFY] [test_views.py](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/caixa_nfse/nfse/tests/test_views.py)

- Mover `TestNFSeConfigView` para usar novas rotas `core:settings_nfse`
- Manter `TestNFSeTestarConexaoView` (rota não muda)

---

## Resumo de Impacto

| Ação | Arquivo |
|------|---------|
| **NOVO** | `templates/core/partials/settings_nfse.html` |
| **MODIFICA** | `core/urls.py` (+1 rota) |
| **MODIFICA** | `core/views.py` (+1 view) |
| **MODIFICA** | `settings.html` (ativa tab) |
| **MODIFICA** | `nfse/urls.py` (remove 1 rota) |
| **MODIFICA** | `nfse/views.py` (remove 1 view) |
| **MODIFICA** | `nfse_list.html` (atualiza link) |
| **MODIFICA** | `test_views.py` (atualiza rotas) |
| **DELETA** | `nfse_config.html` |

## Verification Plan

### Automated Tests
```bash
python -m pytest caixa_nfse/nfse/tests/test_views.py -v
```

### Manual
1. Acessar `/settings/` → clicar aba "NFS-e" → verificar formulário
2. Salvar configuração → toast success
3. Testar Conexão → toast result
4. Verificar que operador **não** vê a aba (gerente only)
5. Verificar que `/nfse/config/` retorna 404
