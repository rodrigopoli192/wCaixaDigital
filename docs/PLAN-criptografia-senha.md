# Criptografia do Campo `senha` em `ConexaoExterna`

Criptografar o campo `ConexaoExterna.senha` que hoje armazena senhas de bancos de dados legados em texto plano. Requisito de segurança / LGPD.

## Abordagem escolhida: Fernet (via `cryptography`)

| Opção | Prós | Contras | Decisão |
|-------|------|---------|---------|
| `django-encrypted-model-fields` | Drop-in field replacement | Projeto descontinuado, última release 2021, incompatível com Django 5.x | ❌ |
| **Fernet nativo** (`cryptography`) | Já instalado (`>=43.0`), criptografia simétrica AES-128-CBC, sem dependência extra | Precisa de helper manual | ✅ |

### Design

```
┌──────────────┐       ┌────────────────┐       ┌──────────────┐
│  Form / View │──────▶│  EncryptedField │──────▶│   Database   │
│  (plaintext) │       │  from_db/to_db  │       │  (ciphertext)│
└──────────────┘       └────────────────┘       └──────────────┘
```

- Campo custom `EncryptedCharField(CharField)` com `from_db_value()` e `get_prep_value()`
- Encrypta ao salvar → Decripta ao ler → **transparente** para views/forms/services
- Chave: `settings.FERNET_KEY` (derivada de `SECRET_KEY` via PBKDF2 para não exigir nova env var)

---

## Análise de Impacto

### Pontos que **NÃO quebram** (transparente)

| Consumidor | Arquivo | Por quê |
|------------|---------|---------|
| `SQLExecutor.get_connection()` | `core/services/sql_executor.py:31,43` | Lê `conexao.senha` → field decripta automaticamente |
| `ConexaoExternaForm` | `core/forms.py:62` | Widget `PasswordInput(render_value=True)` → recebe valor decriptado |
| `ConexaoExternaTestView` | `core/views.py:1123` | Lê senha do `request.POST`, **não do model** → sem impacto |
| Create/Update Views | `core/views.py:887-922` | `form.save()` → field encrypta automaticamente |

### Pontos que **precisam de atenção**

| Item | Detalhe |
|------|---------|
| **Migração de dados** | Senhas existentes em texto plano precisam ser encriptadas (data migration) |
| **`max_length`** | Fernet output é ~2.4x maior que input. `max_length=255` → `max_length=500` |
| **Testes** | ~12 arquivos criam `ConexaoExterna(senha="pass")`. **Continuam funcionando** pois o field encrypta no `get_prep_value` |

> [!IMPORTANT]
> **Risco zero de downtime**: A mudança é 100% transparente via ORM. Nenhuma view, form ou service precisa mudar.

---

## Proposed Changes

### Core Model

#### [NEW] [encrypted_fields.py](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/caixa_nfse/core/encrypted_fields.py)

Custom `EncryptedCharField(CharField)`:
- `get_prep_value(value)` → Fernet encrypt antes de salvar
- `from_db_value(value)` → Fernet decrypt ao ler
- `_get_fernet_key()` → Deriva chave via `PBKDF2(SECRET_KEY)`
- Proteção contra double-encrypt (verifica prefixo `gAAAAA`)

#### [MODIFY] [models.py](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/caixa_nfse/core/models.py)

```diff
-    senha = models.CharField(_("senha"), max_length=255)
+    senha = EncryptedCharField(_("senha"), max_length=500)
```

#### [NEW] Migration: `XXXX_encrypt_conexao_senha`

1. **Schema**: `AlterField` → `EncryptedCharField(max_length=500)`
2. **Data**: `RunPython` → encripta todas as senhas existentes em texto plano

---

### Achado adicional: `Tenant.certificado_senha`

> [!NOTE]
> `Tenant.certificado_senha` (linha 159) também é `CharField(max_length=255)` em texto plano. Podemos aplicar o mesmo `EncryptedCharField` nesta sprint ou em uma futura. **Não está no escopo principal** mas é o mesmo padrão.

---

## Verification Plan

### Automated Tests

```bash
# Rodar todos os testes existentes — devem passar sem alteração
python -m pytest caixa_nfse/core/tests/test_views_conexoes.py -q

# Rodar testes de import que criam ConexaoExterna
python -m pytest caixa_nfse/caixa/tests/test_views_import.py -q
python -m pytest caixa_nfse/caixa/tests/test_views_coverage.py -q

# Novo teste unitário para EncryptedCharField
python -m pytest caixa_nfse/core/tests/test_encrypted_field.py -q
```

**Novo teste** `test_encrypted_field.py`:
- `test_value_is_encrypted_in_db`: Verifica que o valor salvo no banco NÃO é texto plano
- `test_value_is_decrypted_on_read`: Verifica que ao ler, o valor volta ao original
- `test_empty_string_not_encrypted`: String vazia permanece vazia
- `test_none_not_encrypted`: `None` permanece `None`
- `test_no_double_encrypt`: Valor já encriptado não é re-encriptado

### Manual Verification

1. No Django shell: criar `ConexaoExterna` com senha "test123"
2. Verificar via SQL raw que o valor no banco começa com `gAAAAA` (prefixo Fernet)
3. Ler o objeto de volta e confirmar que `conexao.senha == "test123"`
