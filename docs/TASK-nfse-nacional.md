# NFS-e Nacional — Plano de Implementação

## Fase 1: Fundação — Strategy Pattern + Configuração ✅
- [x] `BaseNFSeBackend` com interface padrão (emitir, consultar, cancelar, baixar_danfse)
- [x] `MockBackend` para testes
- [x] `registry.py` com `get_backend(tenant)` e fallback para Mock
- [x] Model `ConfiguracaoNFSe` (backend, ambiente, gerar_nfse_ao_confirmar)
- [x] Celery task `enviar_nfse` com retry

## Fase 2: Portal Nacional Backend (Opção A) ✅
- [x] `xml_builder.py` — Geração XML DPS no padrão nacional
- [x] `xml_signer.py` — Assinatura XMLDSIG com certificado A1
- [x] `api_client.py` — Client HTTP para API REST do Portal Nacional
- [x] `backend.py` — `PortalNacionalBackend` com emitir/consultar/cancelar
- [x] `danfse.py` — Download DANFSe via API
- [x] Import protegido no registry (try/except para httpx)

## Fase 3: Integração com Caixa ✅
- [x] Emissão automática ao confirmar importação (flag `gerar_nfse_ao_confirmar`)
- [x] Vinculação `MovimentoCaixa.nota_fiscal`
- [x] Campos CBS/IBS para reforma tributária
- [x] Livro fiscal de serviços por competência

## Fase 4: Frontend — Templates, UX e Interações ✅
- [x] CRUD NFS-e (list, detail, create, update)
- [x] Enviar, Cancelar, Download XML via HTMX
- [x] Config NFS-e integrada em Configurações do Sistema
- [x] Config dinâmica por backend (Alpine.js x-show)
- [x] Upload de certificado A1 (.pfx) na config
- [x] Testar Conexão (HTMX endpoint)

## Fase 5: Backend Gateway — Focus NFe / TecnoSpeed
- [ ] Pesquisar APIs dos gateways (Focus NFe, TecnoSpeed)
- [ ] `GatewayBackend` base com interface JSON simplificada
- [ ] `FocusNFeBackend` — Integração com Focus NFe API
- [ ] `TecnoSpeedBackend` — Integração com TecnoSpeed API
- [ ] Mapper de dados internos → formato do gateway (JSON)
- [ ] Webhook receiver para callbacks assíncronos
- [ ] Registrar novos backends no `registry.py`
- [ ] Config dinâmica no template (seção Credenciais com Token + Secret)
- [ ] Rastreabilidade: logs de auditoria completos (request/response, timestamps, status)
- [ ] Testes unitários para cada gateway backend

## Fase 6: Produção e DANFSe
- [ ] Validação end-to-end com certificado real (Portal Nacional)
- [ ] Geração/download DANFSe (PDF) com visualização no sistema
- [ ] Monitoramento de certificados vencendo (Celery beat)
- [ ] Retry inteligente com dead-letter queue
- [ ] Dashboard de status de emissão (KPIs: emitidas, rejeitadas, canceladas)
- [ ] Logs e alertas Sentry para falhas de integração
- [ ] Documentação de operação para usuário final
