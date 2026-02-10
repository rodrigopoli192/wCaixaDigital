# Plano de Implementação: Agrupamento de Importação por Protocolo

## Objetivo
Implementar lógica de agrupamento na importação de movimentos via rotinas SQL. Diversos registros retornados com o mesmo número de protocolo devem ser consolidados em um único `MovimentoImportado`, somando os valores financeiros e concatenando as descrições.

## Regras de Negócio (Definidas pelo Usuário)
1.  **Chave de Agrupamento**: `protocolo`.
2.  **Campos Somáveis**: `valor` e todas as taxas/fundos (`iss`, `fundesp`, `emolumento`, `taxa_judiciaria`, etc).
3.  **Campos Não-Somáveis**: `cliente_nome`, `status_item`. Manter o valor do **primeiro** registro encontrado.
4.  **Descrição**:
    *   Deve conter o **Nome da Rotina**.
    *   Deve concatenar as descrições originais das linhas agrupadas.
    *   Formato sugerido: `"{Nome da Rotina} - {Desc1}; {Desc2}"`.

## Arquivos Afetados

### [Importador de Movimentos](file:///c:/Users/Rodrigo/Projetos/wCaixaDigital/caixa_nfse/caixa/services/importador.py)
A classe `ImportadorMovimentos` será modificada no método `salvar_importacao`.

#### Estratégia de Mudança
- Antes de processar a criação dos objetos `MovimentoImportado`, iterar sobre `rows` e construir um dicionário `agrupados`.
- Chave do dicionário: `protocolo` (string normalizada).
- Estrutura do valor acumulado:
  ```python
  {
      "protocolo": "12345",
      "soma_valores": { "valor": Decimal, "iss": Decimal, ... }, # Todos campos TAXA_FIELDS + valor
      "descricoes": set(), # Para evitar repetição na concatenação
      "primeiros_registros": { "cliente_nome": "Fulano", "status_item": "Pago" }
  }
  ```
- Após agrupar, iterar sobre o dicionário para instanciar os objetos `MovimentoImportado`.

## Plano de Verificação

### Testes Manuais
1.  Criar uma Rotina SQL de teste que retorne 3 linhas com o mesmo protocolo e valores diferentes.
2.  Executar a importação.
3.  Verificar se apenas 1 registro foi criado na tabela `caixa_movimentoimportado`.
4.  Confirmar se a `valor` total e as taxas estão somados corretamente.
5.  Confirmar se a descrição está no formato `NomeRotina - Desc1; Desc2`.

### Testes Automatizados
- Criar teste unitário em `caixa_nfse/caixa/tests/test_services.py` simulando o cenário acima.
