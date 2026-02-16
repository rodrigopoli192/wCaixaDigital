import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import IntegrityError
from django.utils import timezone

from caixa_nfse.nfse.models import ConfiguracaoNFSe, StatusNFSe
from caixa_nfse.tests.factories import (
    ConfiguracaoNFSeFactory,
    EventoFiscalFactory,
    NotaFiscalServicoFactory,
    ServicoMunicipalFactory,
    TenantFactory,
)


@pytest.mark.django_db
class TestServicoMunicipalModel:
    """Tests for ServicoMunicipal model."""

    def test_create_servico(self):
        """Should create service code."""
        servico = ServicoMunicipalFactory()
        assert servico.pk is not None
        assert str(servico) == f"{servico.codigo_lc116} - {servico.descricao[:50]}"

    def test_unique_codigo_lc116_municipio(self):
        """Should enforce uniqueness."""
        ServicoMunicipalFactory(codigo_lc116="1.01", municipio_ibge="3550308")
        with pytest.raises(IntegrityError):
            ServicoMunicipalFactory(codigo_lc116="1.01", municipio_ibge="3550308")


@pytest.mark.django_db
class TestNotaFiscalServicoModel:
    """Tests for NotaFiscalServico model."""

    def test_calculation_on_save(self):
        """Should calculate taxes and totals on save."""
        nota = NotaFiscalServicoFactory(
            valor_servicos=Decimal("100.00"),
            aliquota_iss=Decimal("0.05"),  # 5%
            valor_deducoes=Decimal("0.00"),
            iss_retido=False,
        )

        # Base Calculo = 100 - 0 = 100
        # ISS = 100 * 0.05 = 5.00
        # Retencoes (default 0)
        # Liquido = 100 - 0 = 100

        assert nota.base_calculo == Decimal("100.00")
        assert nota.valor_iss == Decimal("5.00")
        assert nota.valor_liquido == Decimal("100.00")

    def test_calculation_with_retention(self):
        """Should subtract ISS from liquid if retained."""
        nota = NotaFiscalServicoFactory(
            valor_servicos=Decimal("100.00"), aliquota_iss=Decimal("0.05"), iss_retido=True
        )

        # ISS = 5.00
        # Retencoes = 5.00 (ISS)
        # Liquido = 100 - 5 = 95

        assert nota.valor_iss == Decimal("5.00")
        assert nota.valor_liquido == Decimal("95.00")

    def test_calculation_with_other_taxes(self):
        """Should subtract federal taxes."""
        nota = NotaFiscalServicoFactory(
            valor_servicos=Decimal("1000.00"),
            valor_pis=Decimal("10.00"),
            valor_cofins=Decimal("30.00"),
            iss_retido=False,
        )
        # Liquido = 1000 - 40 = 960
        assert nota.valor_liquido == Decimal("960.00")

    def test_pode_cancelar(self):
        """Should check cancellation window (30 days) and status."""
        nota = NotaFiscalServicoFactory(
            status=StatusNFSe.AUTORIZADA, data_emissao=timezone.now().date()
        )
        assert nota.pode_cancelar is True

        # Non-authorized cannot cancel (conceptually, or maybe they can cancel a draft? logic says status!=AUTORIZADA -> False)
        nota.status = StatusNFSe.RASCUNHO
        assert nota.pode_cancelar is False

        # Old note
        nota.status = StatusNFSe.AUTORIZADA
        nota.data_emissao = timezone.now().date() - timedelta(days=31)
        assert nota.pode_cancelar is False

    def test_str_representation(self):
        """Should return RPS or NFSe number."""
        nota = NotaFiscalServicoFactory(numero_rps=123, numero_nfse=None)
        assert str(nota) == "RPS 123"

        nota.numero_nfse = 456
        assert str(nota) == "NFS-e 456"

    def test_unique_rps_per_tenant(self):
        """Should enforce unique RPS per tenant."""
        tenant = TenantFactory()
        NotaFiscalServicoFactory(tenant=tenant, numero_rps=10, serie_rps="1")

        with pytest.raises(IntegrityError):
            NotaFiscalServicoFactory(tenant=tenant, numero_rps=10, serie_rps="1")


@pytest.mark.django_db
class TestHardeningFields:
    """Tests for new hardening fields (uuid_transacao, json_retorno_gateway, mensagem_erro)."""

    def test_uuid_transacao_auto_generated(self):
        """uuid_transacao should be auto-generated as a valid UUID4."""
        nota = NotaFiscalServicoFactory()
        assert nota.uuid_transacao is not None
        assert isinstance(nota.uuid_transacao, uuid.UUID)
        assert nota.uuid_transacao.version == 4

    def test_uuid_transacao_unique_per_nota(self):
        """Each nota should get a different uuid_transacao."""
        n1 = NotaFiscalServicoFactory()
        n2 = NotaFiscalServicoFactory()
        assert n1.uuid_transacao != n2.uuid_transacao

    def test_json_retorno_gateway_nullable(self):
        """json_retorno_gateway should accept null and dict values."""
        nota = NotaFiscalServicoFactory()
        assert nota.json_retorno_gateway is None

        nota.json_retorno_gateway = {"status": "autorizado", "numero": 12345}
        nota.save()
        nota.refresh_from_db()
        assert nota.json_retorno_gateway == {"status": "autorizado", "numero": 12345}

    def test_mensagem_erro_saved(self):
        """mensagem_erro should persist and default to empty string."""
        nota = NotaFiscalServicoFactory()
        assert nota.mensagem_erro == ""

        nota.mensagem_erro = "CNPJ inválido no campo tomador"
        nota.save()
        nota.refresh_from_db()
        assert nota.mensagem_erro == "CNPJ inválido no campo tomador"

    def test_encrypted_token_roundtrip(self):
        """api_token and api_secret should encrypt/decrypt transparently."""
        config = ConfiguracaoNFSeFactory(
            api_token="my-secret-token-123",
            api_secret="my-secret-key-456",
        )
        config.refresh_from_db()
        assert config.api_token == "my-secret-token-123"
        assert config.api_secret == "my-secret-key-456"

        # Verify encryption happens via field's get_prep_value
        field = ConfiguracaoNFSe._meta.get_field("api_token")
        db_value = field.get_prep_value("my-secret-token-123")
        assert db_value != "my-secret-token-123"
        assert db_value.startswith("gAAAAA")  # Fernet token prefix


@pytest.mark.django_db
class TestEventoFiscalModel:
    """Tests for EventoFiscal model."""

    def test_create_evento(self):
        """Should create event log."""
        evento = EventoFiscalFactory()
        assert evento.pk is not None
        assert str(evento) == f"{evento.get_tipo_display()} - {evento.nota}"
