"""
Factory classes for generating test data.
"""

from decimal import Decimal

import factory


class TenantFactory(factory.django.DjangoModelFactory):
    """Factory for Tenant model."""

    class Meta:
        model = "core.Tenant"

    razao_social = factory.Sequence(lambda n: f"Empresa {n} Ltda")
    nome_fantasia = factory.Sequence(lambda n: f"Empresa {n}")
    cnpj = factory.Sequence(lambda n: f"{n:014d}")
    inscricao_municipal = factory.Sequence(lambda n: f"{n:06d}")
    email = factory.LazyAttribute(lambda o: f"{o.nome_fantasia.lower().replace(' ', '')}@teste.com")
    telefone = "11999999999"
    logradouro = "Rua Teste"
    numero = "100"
    bairro = "Centro"
    cidade = "São Paulo"
    uf = "SP"
    cep = "01001000"


class UserFactory(factory.django.DjangoModelFactory):
    """Factory for User model."""

    class Meta:
        model = "core.User"

    email = factory.Sequence(lambda n: f"user{n}@teste.com")
    first_name = factory.Faker("first_name", locale="pt_BR")
    last_name = factory.Faker("last_name", locale="pt_BR")
    tenant = factory.SubFactory(TenantFactory)
    password = factory.PostGenerationMethodCall("set_password", "testpass123")
    pode_operar_caixa = True


class CaixaFactory(factory.django.DjangoModelFactory):
    """Factory for Caixa model."""

    class Meta:
        model = "caixa.Caixa"

    tenant = factory.SubFactory(TenantFactory)
    identificador = factory.Sequence(lambda n: f"CAIXA-{n:02d}")
    tipo = "FISICO"
    ativo = True


class FormaPagamentoFactory(factory.django.DjangoModelFactory):
    """Factory for FormaPagamento model."""

    class Meta:
        model = "core.FormaPagamento"

    tenant = factory.SubFactory(TenantFactory)
    nome = "Dinheiro"
    # codigo = "01" # Field does not exist on model
    ativo = True


class AberturaCaixaFactory(factory.django.DjangoModelFactory):
    """Factory for AberturaCaixa model."""

    class Meta:
        model = "caixa.AberturaCaixa"

    tenant = factory.LazyAttribute(lambda o: o.caixa.tenant)
    caixa = factory.SubFactory(CaixaFactory)
    operador = factory.SubFactory(UserFactory)
    saldo_abertura = Decimal("100.00")
    fundo_troco = Decimal("50.00")


class FechamentoCaixaFactory(factory.django.DjangoModelFactory):
    """Factory for FechamentoCaixa model."""

    class Meta:
        model = "caixa.FechamentoCaixa"

    tenant = factory.LazyAttribute(lambda o: o.abertura.caixa.tenant)
    abertura = factory.SubFactory(AberturaCaixaFactory)
    operador = factory.SubFactory(UserFactory)
    saldo_sistema = Decimal("100.00")
    saldo_informado = Decimal("100.00")
    diferenca = Decimal("0.00")
    status = "FECHADO"


class MovimentoCaixaFactory(factory.django.DjangoModelFactory):
    """Factory for MovimentoCaixa model."""

    class Meta:
        model = "caixa.MovimentoCaixa"

    tenant = factory.LazyAttribute(lambda o: o.abertura.caixa.tenant)
    abertura = factory.SubFactory(AberturaCaixaFactory)
    tipo = "ENTRADA"
    forma_pagamento = factory.SubFactory(FormaPagamentoFactory)
    valor = Decimal("50.00")
    descricao = "Movimento de teste"
    protocolo = ""
    status_item = ""
    quantidade = 1
    emolumento = Decimal("0.00")
    taxa_judiciaria = Decimal("0.00")


class PlanoContasFactory(factory.django.DjangoModelFactory):
    """Factory for PlanoContas model."""

    class Meta:
        model = "contabil.PlanoContas"

    tenant = factory.SubFactory(TenantFactory)
    codigo = factory.Sequence(lambda n: f"1.01.{n:03d}")
    descricao = factory.Sequence(lambda n: f"Conta Contábil {n}")
    tipo = "ATIVO"
    natureza = "D"
    nivel = 3
    permite_lancamento = True
    ativo = True


class CentroCustoFactory(factory.django.DjangoModelFactory):
    """Factory for CentroCusto model."""

    class Meta:
        model = "contabil.CentroCusto"

    tenant = factory.SubFactory(TenantFactory)
    codigo = factory.Sequence(lambda n: f"CC-{n:03d}")
    descricao = factory.Sequence(lambda n: f"Centro de Custo {n}")
    ativo = True


class LancamentoContabilFactory(factory.django.DjangoModelFactory):
    """Factory for LancamentoContabil model."""

    class Meta:
        model = "contabil.LancamentoContabil"

    tenant = factory.SubFactory(TenantFactory)
    data_lancamento = factory.Faker("date_between", start_date="-1y", end_date="today")
    data_competencia = factory.LazyAttribute(lambda o: o.data_lancamento)
    historico = "Lançamento de teste"
    valor_total = Decimal("100.00")
    origem_tipo = "manual"


class PartidaLancamentoFactory(factory.django.DjangoModelFactory):
    """Factory for PartidaLancamento model."""

    class Meta:
        model = "contabil.PartidaLancamento"

    lancamento = factory.SubFactory(LancamentoContabilFactory)
    conta = factory.SubFactory(PlanoContasFactory)
    centro_custo = factory.SubFactory(CentroCustoFactory)
    tipo = "D"
    valor = Decimal("100.00")


class ClienteFactory(factory.django.DjangoModelFactory):
    """Factory for Cliente model."""

    class Meta:
        model = "clientes.Cliente"

    tenant = factory.SubFactory(TenantFactory)
    tipo_pessoa = "PF"
    cpf_cnpj = factory.Faker("cpf", locale="pt_BR")
    razao_social = factory.Faker("name", locale="pt_BR")
    nome_fantasia = factory.Faker("company", locale="pt_BR")
    email = factory.Faker("email")
    telefone = "11999999999"
    ativo = True


class ServicoMunicipalFactory(factory.django.DjangoModelFactory):
    """Factory for ServicoMunicipal model."""

    class Meta:
        model = "nfse.ServicoMunicipal"

    codigo_lc116 = factory.Sequence(lambda n: f"1.{n:02d}")
    codigo_municipal = factory.Sequence(lambda n: f"{n:04d}")
    descricao = factory.Sequence(lambda n: f"Serviço Municipal {n}")
    aliquota_iss = Decimal("0.05")
    municipio_ibge = "3550308"  # SP


class NotaFiscalServicoFactory(factory.django.DjangoModelFactory):
    """Factory for NotaFiscalServico model."""

    class Meta:
        model = "nfse.NotaFiscalServico"

    tenant = factory.SubFactory(TenantFactory)
    cliente = factory.SubFactory(ClienteFactory)
    numero_rps = factory.Sequence(lambda n: n + 1)
    serie_rps = "1"
    status = "RASCUNHO"
    servico = factory.SubFactory(ServicoMunicipalFactory)
    discriminacao = "Serviço prestado"
    valor_servicos = Decimal("100.00")
    aliquota_iss = Decimal("0.05")
    competencia = factory.Faker("date_between", start_date="-1y", end_date="today")
    local_prestacao_ibge = "3550308"


class EventoFiscalFactory(factory.django.DjangoModelFactory):
    """Factory for EventoFiscal model."""

    class Meta:
        model = "nfse.EventoFiscal"

    tenant = factory.SubFactory(TenantFactory)
    nota = factory.SubFactory(NotaFiscalServicoFactory)
    tipo = "GERACAO"
    mensagem = "Evento de teste"


class ConfiguracaoNFSeFactory(factory.django.DjangoModelFactory):
    """Factory for ConfiguracaoNFSe model."""

    class Meta:
        model = "nfse.ConfiguracaoNFSe"

    tenant = factory.SubFactory(TenantFactory)
    backend = "mock"
    ambiente = "HOMOLOGACAO"
    gerar_nfse_ao_confirmar = False


class RegistroAuditoriaFactory(factory.django.DjangoModelFactory):
    """Factory for RegistroAuditoria model."""

    class Meta:
        model = "auditoria.RegistroAuditoria"

    tenant = factory.SubFactory(TenantFactory)
    tabela = "nfse_notafiscalservico"
    registro_id = factory.Faker("uuid4")
    acao = "CREATE"
    usuario = factory.SubFactory(UserFactory)
    ip_address = "127.0.0.1"
    dados_antes = {}
    dados_depois = {"status": "RASCUNHO"}
