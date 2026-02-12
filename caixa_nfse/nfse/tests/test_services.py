"""
Tests for nfse/services.py — criar_nfse_de_movimento.
"""

from decimal import Decimal

import pytest
from django.utils import timezone

from caixa_nfse.nfse.models import StatusNFSe
from caixa_nfse.nfse.services import criar_nfse_de_movimento
from caixa_nfse.tests.factories import (
    ClienteFactory,
    ConfiguracaoNFSeFactory,
    MovimentoCaixaFactory,
    ServicoMunicipalFactory,
    TenantFactory,
)


@pytest.mark.django_db
class TestCriarNfseDeMovimento:
    def setup_method(self):
        self.tenant = TenantFactory()
        self.cliente = ClienteFactory(tenant=self.tenant)
        self.servico = ServicoMunicipalFactory()
        self.movimento = MovimentoCaixaFactory(
            abertura__caixa__tenant=self.tenant,
            cliente=self.cliente,
            valor=Decimal("200.00"),
            descricao="Registro de imóvel",
            protocolo="12345",
        )

    def test_cria_nota_com_dados_corretos(self):
        nota = criar_nfse_de_movimento(self.movimento, self.servico)

        assert nota.pk is not None
        assert nota.tenant == self.tenant
        assert nota.cliente == self.cliente
        assert nota.servico == self.servico
        assert nota.valor_servicos == Decimal("200.00")
        assert nota.status == StatusNFSe.RASCUNHO
        assert nota.discriminacao == "Registro de imóvel"
        assert nota.local_prestacao_ibge == self.servico.municipio_ibge

    def test_vincula_movimento_a_nota(self):
        nota = criar_nfse_de_movimento(self.movimento, self.servico)

        self.movimento.refresh_from_db()
        assert self.movimento.nota_fiscal == nota

    def test_gera_numero_rps(self):
        rps_antes = self.tenant.nfse_ultimo_rps
        nota = criar_nfse_de_movimento(self.movimento, self.servico)

        assert nota.numero_rps == rps_antes + 1

    def test_calcula_valores_derivados(self):
        nota = criar_nfse_de_movimento(self.movimento, self.servico)

        # save() calcula: base_calculo, valor_iss, valor_liquido
        assert nota.base_calculo == nota.valor_servicos - nota.valor_deducoes
        assert nota.valor_iss == nota.base_calculo * nota.aliquota_iss

    def test_usa_config_ambiente_backend(self):
        ConfiguracaoNFSeFactory(
            tenant=self.tenant,
            ambiente="PRODUCAO",
            backend="portal_nacional",
        )

        nota = criar_nfse_de_movimento(self.movimento, self.servico)

        assert nota.ambiente == "PRODUCAO"
        assert nota.backend_utilizado == "portal_nacional"

    def test_fallback_sem_config(self):
        nota = criar_nfse_de_movimento(self.movimento, self.servico)

        assert nota.ambiente == "HOMOLOGACAO"
        assert nota.backend_utilizado == "mock"

    def test_busca_servico_automaticamente(self):
        # servico already exists from setup
        nota = criar_nfse_de_movimento(self.movimento)

        assert nota.servico == self.servico

    def test_erro_sem_cliente(self):
        movimento_sem_cliente = MovimentoCaixaFactory(
            abertura__caixa__tenant=self.tenant,
            cliente=None,
            valor=Decimal("100.00"),
        )

        with pytest.raises(ValueError, match="sem cliente vinculado"):
            criar_nfse_de_movimento(movimento_sem_cliente, self.servico)

    def test_erro_sem_servico_cadastrado(self):
        # Delete all ServicoMunicipal
        from caixa_nfse.nfse.models import ServicoMunicipal

        ServicoMunicipal.objects.all().delete()

        with pytest.raises(ValueError, match="Nenhum serviço municipal"):
            criar_nfse_de_movimento(self.movimento)

    def test_discriminacao_fallback_protocolo(self):
        movimento = MovimentoCaixaFactory(
            abertura__caixa__tenant=self.tenant,
            cliente=self.cliente,
            valor=Decimal("100.00"),
            descricao="",
            protocolo="P-999",
        )

        nota = criar_nfse_de_movimento(movimento, self.servico)
        assert "P-999" in nota.discriminacao

    def test_competencia_primeiro_dia_mes(self):
        nota = criar_nfse_de_movimento(self.movimento, self.servico)

        assert nota.competencia.day == 1
        assert nota.competencia.month == timezone.now().month
