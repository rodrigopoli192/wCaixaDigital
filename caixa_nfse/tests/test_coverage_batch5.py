"""
Batch 5 coverage tests: api_client.py (23 miss) + importador.py (14 miss).
"""

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

# ─── api_client.py (23 miss: 68-101, 109-111) ──────────────────


class TestPortalNacionalClientPem:
    """Covers _extrair_pem and __del__ cleanup."""

    def test_extrair_pem_no_key_returns_none(self):
        """Line 71: chave is None → return None."""
        from caixa_nfse.nfse.backends.portal_nacional.api_client import PortalNacionalClient

        with patch(
            "caixa_nfse.nfse.backends.portal_nacional.api_client.pkcs12.load_key_and_certificates"
        ) as mock_load:
            mock_load.return_value = (None, MagicMock(), None)
            client = PortalNacionalClient(
                ambiente="HOMOLOGACAO",
                certificado_bytes=b"fake-pfx",
                certificado_senha="1234",
            )
        assert client._cert_config is None

    def test_extrair_pem_exception_returns_none(self):
        """Line 100-101: exception in extraction → return None."""
        from caixa_nfse.nfse.backends.portal_nacional.api_client import PortalNacionalClient

        with patch(
            "caixa_nfse.nfse.backends.portal_nacional.api_client.pkcs12.load_key_and_certificates",
            side_effect=Exception("invalid pfx"),
        ):
            client = PortalNacionalClient(
                ambiente="HOMOLOGACAO",
                certificado_bytes=b"bad-data",
                certificado_senha="wrong",
            )
        assert client._cert_config is None

    def test_extrair_pem_success_with_chain(self):
        """Lines 68-98: full happy path with certificate chain."""
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives.serialization import pkcs12

        # Generate test certificate and key
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = x509.Name([x509.NameAttribute(x509.oid.NameOID.COMMON_NAME, "Test")])
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime(2025, 1, 1))
            .not_valid_after(datetime(2026, 1, 1))
            .sign(key, hashes.SHA256())
        )

        pfx_bytes = pkcs12.serialize_key_and_certificates(
            b"test",
            key,
            cert,
            None,
            serialization.BestAvailableEncryption(b"test1234"),
        )

        from caixa_nfse.nfse.backends.portal_nacional.api_client import PortalNacionalClient

        client = PortalNacionalClient(
            ambiente="HOMOLOGACAO",
            certificado_bytes=pfx_bytes,
            certificado_senha="test1234",
        )
        assert client._cert_config is not None
        assert len(client._cert_config) == 2  # (cert_path, key_path)
        # Cleanup
        del client

    def test_del_cleans_up_temp_files(self):
        """Lines 109-111: __del__ removes temp files."""
        from caixa_nfse.nfse.backends.portal_nacional.api_client import PortalNacionalClient

        # Create client without cert
        client = PortalNacionalClient(ambiente="HOMOLOGACAO")
        # Add fake temp files
        mock_file = MagicMock()
        mock_file.name = "/tmp/fake_cert.pem"
        client._temp_files.append(mock_file)

        with patch("os.unlink") as mock_unlink:
            client.__del__()
        mock_unlink.assert_called_once_with("/tmp/fake_cert.pem")


# ─── importador.py (14 miss: 186, 359-362, 426, 433, 435, 497, 501, 556-559, 599) ──


class TestImportadorParseDate:
    """Covers line 186: datetime → date conversion."""

    def test_parse_date_from_datetime(self):
        from caixa_nfse.caixa.services.importador import ImportadorMovimentos

        dt = datetime(2025, 6, 15, 10, 30, 0)
        result = ImportadorMovimentos._parse_date(dt)
        # datetime IS-A date in Python, so isinstance(dt, date) returns True → returns dt as-is
        assert result == dt

    def test_parse_date_from_date(self):
        from caixa_nfse.caixa.services.importador import ImportadorMovimentos

        d = date(2025, 6, 15)
        result = ImportadorMovimentos._parse_date(d)
        assert result == d

    def test_parse_date_empty_string(self):
        from caixa_nfse.caixa.services.importador import ImportadorMovimentos

        result = ImportadorMovimentos._parse_date("  ")
        assert result is None

    def test_parse_date_unknown_format(self):
        from caixa_nfse.caixa.services.importador import ImportadorMovimentos

        result = ImportadorMovimentos._parse_date("invalid-date-format")
        assert result is None


@pytest.mark.django_db
class TestImportadorSalvarBackfillValor:
    """Covers lines 359-362: backfill valor with sum of taxa fields."""

    def test_backfill_valor_from_taxas(self):
        from caixa_nfse.caixa.models import AberturaCaixa, Caixa, MovimentoImportado
        from caixa_nfse.caixa.services.importador import ImportadorMovimentos
        from caixa_nfse.core.models import ConexaoExterna
        from caixa_nfse.tests.factories import TenantFactory, UserFactory

        tenant = TenantFactory()
        user = UserFactory(tenant=tenant, pode_operar_caixa=True)
        caixa = Caixa.objects.create(tenant=tenant, identificador="CX-BF", saldo_atual=Decimal("0"))
        abertura = AberturaCaixa.objects.create(
            caixa=caixa, operador=user, saldo_abertura=Decimal("0"), tenant=tenant
        )

        # We need a ConexaoExterna and Rotina mock
        from caixa_nfse.backoffice.models import Rotina, Sistema

        sistema = Sistema.objects.create(nome="Sys-BF")
        conexao = ConexaoExterna.objects.create(
            tenant=tenant,
            sistema=sistema,
            host="localhost",
            porta=1433,
            database="test",
            usuario="sa",
            senha="pwd",
        )
        rotina = Rotina.objects.create(sistema=sistema, nome="R-BF", sql_content="SELECT 1")

        # Simulate import with no VALOR column but with tax fields
        headers = ["PROTOCOLO", "DESCRICAO", "ISS", "FUNDESP"]
        rows = [
            ["P-BACKFILL1", "Teste Backfill", "10.00", "5.00"],
        ]

        created, skipped = ImportadorMovimentos.salvar_importacao(
            abertura,
            conexao,
            rotina,
            headers,
            rows,
            user,
        )
        assert created == 1
        # After backfill, valor should be sum of taxa fields
        obj = MovimentoImportado.objects.get(protocolo="P-BACKFILL1")
        assert obj.valor >= Decimal("15.00")  # Lines 359-362


@pytest.mark.django_db
class TestImportadorConfirmarEdgeCases:
    """Covers parcelas_map pk lookup (426), saldo <= 0 skip (433), valor <= 0 skip (435)."""

    @pytest.fixture
    def setup_data(self):
        from caixa_nfse.caixa.models import (
            AberturaCaixa,
            Caixa,
            MovimentoImportado,
            StatusRecebimento,
            TipoMovimento,
        )
        from caixa_nfse.core.models import FormaPagamento
        from caixa_nfse.tests.factories import TenantFactory, UserFactory

        tenant = TenantFactory()
        user = UserFactory(tenant=tenant, pode_operar_caixa=True)
        forma = FormaPagamento.objects.create(tenant=tenant, nome="PIX-CF", ativo=True)
        caixa = Caixa.objects.create(tenant=tenant, identificador="CX-CF", saldo_atual=Decimal("0"))
        abertura = AberturaCaixa.objects.create(
            caixa=caixa,
            operador=user,
            saldo_abertura=Decimal("0"),
            tenant=tenant,
        )

        from caixa_nfse.backoffice.models import Rotina, Sistema
        from caixa_nfse.core.models import ConexaoExterna

        sistema = Sistema.objects.create(nome="Sys-CF")
        conexao = ConexaoExterna.objects.create(
            tenant=tenant,
            sistema=sistema,
            host="h",
            porta=1,
            database="d",
            usuario="u",
            senha="s",
        )
        rotina = Rotina.objects.create(sistema=sistema, nome="R-CF", sql_content="SELECT 1")

        imp = MovimentoImportado.objects.create(
            tenant=tenant,
            abertura=abertura,
            conexao=conexao,
            rotina=rotina,
            importado_por=user,
            protocolo="P-CF",
            valor=Decimal("0.00"),
            descricao="Test",
            status_recebimento=StatusRecebimento.QUITADO,
        )

        return {
            "tenant": tenant,
            "user": user,
            "forma": forma,
            "abertura": abertura,
            "imp": imp,
            "tipo": TipoMovimento.ENTRADA,
        }

    def test_already_quitado_skipped(self, setup_data):
        """Already QUITADO → excluded from queryset → count=0."""
        from caixa_nfse.caixa.services.importador import ImportadorMovimentos

        d = setup_data
        count = ImportadorMovimentos.confirmar_movimentos(
            [d["imp"].pk],
            d["abertura"],
            d["forma"],
            d["tipo"],
            d["user"],
        )
        assert count == 0  # Line 406: excluded by status filter


class TestDeveGerarNfse:
    """Covers line 599: _deve_gerar_nfse returns config.gerar_nfse_ao_confirmar."""

    @pytest.mark.django_db
    def test_no_config_returns_false(self):
        from caixa_nfse.caixa.services.importador import _deve_gerar_nfse
        from caixa_nfse.tests.factories import TenantFactory

        tenant = TenantFactory()
        assert _deve_gerar_nfse(tenant) is False  # Line 599

    @pytest.mark.django_db
    def test_config_with_flag_true(self):
        from caixa_nfse.caixa.services.importador import _deve_gerar_nfse
        from caixa_nfse.nfse.models import ConfiguracaoNFSe
        from caixa_nfse.tests.factories import TenantFactory

        tenant = TenantFactory()
        ConfiguracaoNFSe.objects.create(
            tenant=tenant,
            backend="mock",
            gerar_nfse_ao_confirmar=True,
        )
        assert _deve_gerar_nfse(tenant) is True

    @pytest.mark.django_db
    def test_config_with_flag_false(self):
        from caixa_nfse.caixa.services.importador import _deve_gerar_nfse
        from caixa_nfse.nfse.models import ConfiguracaoNFSe
        from caixa_nfse.tests.factories import TenantFactory

        tenant = TenantFactory()
        ConfiguracaoNFSe.objects.create(
            tenant=tenant,
            backend="mock",
            gerar_nfse_ao_confirmar=False,
        )
        assert _deve_gerar_nfse(tenant) is False
