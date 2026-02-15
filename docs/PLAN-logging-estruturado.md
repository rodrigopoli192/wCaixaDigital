# Logging Estruturado (JSON) + django.server

Configurar logging estruturado em JSON para observabilidade e centralização de logs. Atualmente os logs usam formatação de texto simples e não incluem contexto de request (tenant, user, request_id).

## Diagnóstico Atual

| Aspecto | Estado Atual | Problema |
|---------|-------------|----------|
| **Formato** | Texto simples (`{levelname} {asctime} {module}`) | Não parseável por ferramentas (ELK, CloudWatch, Datadog) |
| **Contexto** | Sem tenant/user/request_id | Impossível correlacionar logs de uma mesma requisição |
| **django.server** | Não configurado | Logs de request HTTP vão para stderr sem formato |
| **Handlers** | `console` + `file` (RotatingFileHandler) | Arquivo rotaciona mas sem formato estruturado |
| **Uso existente** | 18 módulos com `logger = logging.getLogger(__name__)` | ✅ Padrão correto — NÃO precisa alterar código |

### Loggers existentes (18 módulos)

```
caixa_nfse.nfse.signals         caixa_nfse.nfse.services
caixa_nfse.nfse.tasks           caixa_nfse.nfse.webhook
caixa_nfse.nfse.views           caixa_nfse.nfse.reports
caixa_nfse.nfse.backends.*      (6 módulos)
caixa_nfse.caixa.views          caixa_nfse.caixa.views_editar_saldo
caixa_nfse.caixa.services.importador
caixa_nfse.auditoria.signals    caixa_nfse.auditoria.auth_signals
```

---

## Proposed Changes

### Dependência

#### [MODIFY] [pyproject.toml](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/pyproject.toml)

Adicionar `python-json-logger>=3.0` às dependências. Pacote leve (zero deps) que fornece o `JsonFormatter`.

---

### Settings

#### [MODIFY] [base.py](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/caixa_nfse/settings/base.py)

Reescrever o bloco `LOGGING` (linhas 217-260):

```python
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.json.JsonFormatter",
            "fmt": "%(asctime)s %(levelname)s %(name)s %(message)s",
            "rename_fields": {"asctime": "timestamp", "levelname": "level", "name": "logger"},
        },
        "simple": {
            "format": "{levelname} {asctime} {name} {message}",
            "style": "{",
        },
    },
    "filters": {
        "request_context": {
            "()": "caixa_nfse.core.logging_filters.RequestContextFilter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
            "filters": ["request_context"],
        },
        "file_json": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": BASE_DIR / "logs" / "app.json.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 10,
            "formatter": "json",
            "filters": ["request_context"],
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file_json"],
            "level": config("DJANGO_LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
        "django.server": {
            "handlers": ["console", "file_json"],
            "level": "INFO",
            "propagate": False,
        },
        "caixa_nfse": {
            "handlers": ["console", "file_json"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}
```

**Mudanças-chave:**
1. Novo formatter `json` usando `python-json-logger`
2. Novo filter `request_context` para injetar `tenant_id`, `user_id`, `request_id`
3. Handler `file_json` grava JSON estruturado em `logs/app.json.log`
4. Logger `django.server` adicionado explicitamente
5. Console mantém formato legível (`simple`) para desenvolvimento

---

### Middleware

#### [NEW] [logging_filters.py](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/caixa_nfse/core/logging_filters.py)

Logging filter que injeta contexto de request em cada log record:

```python
import logging
import threading
import uuid

_request_context = threading.local()

class RequestContextFilter(logging.Filter):
    def filter(self, record):
        record.request_id = getattr(_request_context, "request_id", "-")
        record.tenant_id = getattr(_request_context, "tenant_id", "-")
        record.user_id = getattr(_request_context, "user_id", "-")
        return True
```

#### [NEW] [logging_middleware.py](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/caixa_nfse/core/logging_middleware.py)

Middleware Django que popula o contexto de request:

```python
class RequestLoggingMiddleware:
    def __call__(self, request):
        _request_context.request_id = str(uuid.uuid4())[:8]
        _request_context.user_id = str(getattr(request.user, "pk", "-"))
        _request_context.tenant_id = str(getattr(request.user, "tenant_id", "-"))
        response = self.get_response(request)
        response["X-Request-ID"] = _request_context.request_id
        return response
```

#### [MODIFY] [base.py](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/caixa_nfse/settings/base.py)

Adicionar `RequestLoggingMiddleware` ao `MIDDLEWARE` (após `AuthenticationMiddleware` para ter acesso a `request.user`):

```diff
 "django.contrib.auth.middleware.AuthenticationMiddleware",
+"caixa_nfse.core.logging_middleware.RequestLoggingMiddleware",
 "django.contrib.messages.middleware.MessageMiddleware",
```

---

### Overrides por ambiente

#### [MODIFY] [local.py](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/caixa_nfse/settings/local.py)

```diff
-LOGGING["handlers"]["file"] = {
-    "class": "logging.FileHandler",
-    "filename": BASE_DIR / "logs" / "django_local.log",
-    "formatter": "verbose",
-}
+# Local: usar FileHandler simples (Windows) + formato JSON
+LOGGING["handlers"]["file_json"] = {
+    "class": "logging.FileHandler",
+    "filename": BASE_DIR / "logs" / "app.json.log",
+    "formatter": "json",
+    "filters": ["request_context"],
+}
```

#### [MODIFY] [production.py](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/caixa_nfse/settings/production.py)

```diff
-LOGGING["handlers"]["file"]["level"] = "WARNING"
+# Produção: console também em JSON para captura por container runtime
+LOGGING["handlers"]["console"]["formatter"] = "json"
+LOGGING["handlers"]["file_json"]["level"] = "WARNING"
```

#### [MODIFY] [test.py](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/caixa_nfse/settings/test.py)

Sem alteração — já substitui o LOGGING inteiro com `CRITICAL` level.

---

## Impacto

| Item | Impacto |
|------|---------|
| **Código da aplicação** | **ZERO** — os 18 módulos usam `logger.info()/error()` que é 100% compatível |
| **Dependência nova** | `python-json-logger>=3.0` (leve, sem subdeps) |
| **Middleware** | 1 novo middleware, ~15 linhas |
| **Formato no console** | Mantém texto legível em dev, JSON em produção |
| **Formato em arquivo** | JSON estruturado com `request_id`, `tenant_id`, `user_id` |

---

## Resultado esperado

### Antes (texto plano)
```
INFO 2026-02-15 14:30:01 services NFS-e emitida com sucesso
```

### Depois (JSON em arquivo)
```json
{
  "timestamp": "2026-02-15T14:30:01.123",
  "level": "INFO",
  "logger": "caixa_nfse.nfse.services",
  "message": "NFS-e emitida com sucesso",
  "request_id": "a1b2c3d4",
  "tenant_id": "uuid-do-tenant",
  "user_id": "uuid-do-user"
}
```

---

## Verification Plan

### Automated Tests

```bash
# 1. Testes existentes devem continuar passando
python -m pytest caixa_nfse/ -q --tb=line

# 2. Novo teste para o logging filter e middleware
python -m pytest caixa_nfse/core/tests/test_logging.py -v
```

**Novo** `test_logging.py`:
- `test_request_context_filter_adds_fields`: Verifica que o filter adiciona `request_id`, `tenant_id`, `user_id`
- `test_middleware_sets_request_id_header`: Verifica header `X-Request-ID` na response
- `test_json_formatter_output`: Verifica que output é JSON válido com campos esperados

### Manual Verification

1. Rodar `python manage.py runserver`, fazer login
2. Verificar que `logs/app.json.log` contém linhas JSON válidas
3. Verificar que cada linha tem `request_id`, `tenant_id`, `user_id`
4. Verificar console continua legível (formato `simple`)
