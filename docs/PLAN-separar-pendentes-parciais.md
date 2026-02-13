# Separar Importações Pendentes vs Parcialmente Pagos

## Problema

A seção "Movimentos Importados (Pendentes)" mistura dois conceitos distintos:
- **Importações novas** (`confirmado=False`, `status=PENDENTE`) — nunca foram confirmadas
- **Protocolos parcialmente pagos** (`confirmado=True`, `status=PARCIAL`) — já confirmados mas com saldo restante

O `ListaImportadosView.get_queryset()` usa `.exclude(status_recebimento=QUITADO)` que retorna ambos misturados.

## Solução

Separar em **duas seções visuais distintas** na mesma página de movimentos.

---

## Proposed Changes

### Backend — View

#### [MODIFY] [views.py](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/caixa_nfse/caixa/views.py)

No `ListaImportadosView.get_context_data()`:

1. Filtrar `importados` (queryset existente) em 3 grupos:
   - `pendentes_novos` = `confirmado=False` (importações nunca confirmadas)
   - `parciais` = `status_recebimento=PARCIAL, confirmado=True` (já confirmados, saldo pendente)
2. Manter separação por sessão apenas para `pendentes_novos`
3. Adicionar `parciais` ao contexto como variável separada

```python
# No get_context_data:
importados = list(context["importados"])
pendentes_novos = [i for i in importados if not i.confirmado]
parciais = [i for i in importados if i.confirmado and i.status_recebimento == 'PARCIAL']

# Sessão split apenas para novos
pendentes_anteriores = [i for i in pendentes_novos if i.importado_em < abertura.data_hora]
importados_sessao_atual = [i for i in pendentes_novos if i.importado_em >= abertura.data_hora]

context["pendentes_anteriores"] = pendentes_anteriores
context["importados_sessao_atual"] = importados_sessao_atual 
context["parciais"] = parciais
# Override importados to only include pendentes_novos (for counter/select-all)
context["importados"] = pendentes_novos
```

---

### Frontend — Template de Importados

#### [MODIFY] [importados_list.html](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/templates/caixa/partials/importados_list.html)

Adicionar uma **terceira seção** entre as importações e o empty state:

```
📦 Pendentes de Sessões Anteriores  (existente)
📥 Importados Desta Sessão          (existente)
⚠️ Parcialmente Pagos               (NOVA SEÇÃO)
```

A seção "Parcialmente Pagos":
- Ícone: `hourglass_top` (amber)
- Título: "Aguardando Saldo Restante"
- Badge de contagem
- Cards com `show_checkbox=True` (para poder completar o pagamento)
- Barra de progresso visível (já existe no card para status PARCIAL)

---

### Frontend — Template do Card

#### [MODIFY] [_movimento_card.html](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/templates/caixa/partials/_movimento_card.html)

Nenhuma mudança necessária — o card já renderiza:
- Badge `PARCIAL (X%)` quando `status_recebimento == 'PARCIAL'`
- Progress bar com valor recebido / total
- Input de "Valor Parcela" quando `show_origem and status != QUITADO`

---

### Frontend — Seção Pai

#### [MODIFY] [movimento_list.html](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/templates/caixa/movimento_list.html)

Renomear a seção de "Movimentos Importados (Pendentes)" para algo mais claro:
- Título: "Importações & Pendências"
- Ou manter "Movimentos Importados" (sem "(Pendentes)") já que agora tem sub-seções

---

## Verification Plan

### Visual
1. Importar novos protocolos → aparecem apenas em "Importados Desta Sessão"
2. Confirmar parcialmente → saem de "Importados" e aparecem em "Aguardando Saldo Restante"
3. Completar pagamento → desaparecem completamente (QUITADO)
4. Protocolos 1823 e 12402 (status PARCIAL) devem aparecer APENAS em "Aguardando Saldo Restante"

### Funcional
- Select-all deve abranger APENAS pendentes novos OU parciais (não misturar)
- Confirmar parcial deve atualizar saldo e status corretamente
- Counter de seleção deve refletir apenas o grupo ativo
