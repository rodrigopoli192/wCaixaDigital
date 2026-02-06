import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from caixa_nfse.clientes.models import TipoPessoa
from caixa_nfse.tests.factories import ClienteFactory, TenantFactory


@pytest.mark.django_db
class TestClienteModel:
    """Tests for Cliente model."""

    def test_create_cliente_pf(self):
        """Should create a PF customer."""
        cliente = ClienteFactory(tipo_pessoa=TipoPessoa.PF)
        assert cliente.pk is not None
        assert cliente.tipo_pessoa == TipoPessoa.PF
        assert str(cliente) == f"{cliente.razao_social} ({cliente.cpf_cnpj})"
        assert cliente.cpf_cnpj_hash is not None

    def test_valid_documents(self):
        """Should validate correct CPF and CNPJ."""
        # PF
        c_pf = ClienteFactory.build(tipo_pessoa=TipoPessoa.PF)  # Factory uses valid CPF
        c_pf.full_clean()  # Should result in validation success (return True)

        # PJ
        c_pj = ClienteFactory.build(tipo_pessoa=TipoPessoa.PJ, cpf_cnpj="59461148000109")
        c_pj.full_clean()

    def test_create_cliente_pj(self):
        """Should create a PJ customer."""
        cliente = ClienteFactory(
            tipo_pessoa=TipoPessoa.PJ,
            cpf_cnpj="59461148000109",  # Valid CNPJ generated
            razao_social="Empresa Teste Ltda",
        )
        assert cliente.pk is not None
        assert cliente.tipo_pessoa == TipoPessoa.PJ

    def test_invalid_cpf(self):
        """Should raise ValidationError for invalid CPF."""
        cliente = ClienteFactory.build(tipo_pessoa=TipoPessoa.PF, cpf_cnpj="11111111111")
        with pytest.raises(ValidationError) as exc:
            cliente.full_clean()
        assert "CPF inválido" in str(exc.value)

    def test_invalid_cnpj(self):
        """Should raise ValidationError for invalid CNPJ."""
        cliente = ClienteFactory.build(tipo_pessoa=TipoPessoa.PJ, cpf_cnpj="00000000000000")
        with pytest.raises(ValidationError) as exc:
            cliente.full_clean()
        assert "CNPJ inválido" in str(exc.value)

    def test_invalid_cpf_checksum(self):
        """Should raise ValidationError for invalid CPF checksum."""
        # 12345678909 is valid checksum? No.
        # But let's use a definitely invalid one that is not repeating.
        # "12345678900"
        cliente = ClienteFactory.build(tipo_pessoa=TipoPessoa.PF, cpf_cnpj="12345678900")
        with pytest.raises(ValidationError) as exc:
            cliente.full_clean()
        assert "CPF inválido" in str(exc.value)

    def test_invalid_cnpj_checksum(self):
        """Should raise ValidationError for invalid CNPJ checksum."""
        # "12345678000100" -> likely invalid
        cliente = ClienteFactory.build(tipo_pessoa=TipoPessoa.PJ, cpf_cnpj="12345678000100")
        with pytest.raises(ValidationError) as exc:
            cliente.full_clean()
        assert "CNPJ inválido" in str(exc.value)

    def test_get_absolute_url(self):
        """Should return absolute url."""
        cliente = ClienteFactory()
        assert cliente.get_absolute_url() == f"/clientes/{cliente.pk}/"

    def test_documento_formatado_fallback(self):
        """Should return raw document if length is unknown."""
        cliente = ClienteFactory(cpf_cnpj="123")
        assert cliente.documento_formatado == "123"

    def test_unique_document_per_tenant(self):
        """Should enforce unique document per tenant."""
        tenant = TenantFactory()

        client_1 = ClienteFactory(tenant=tenant)

        with pytest.raises(IntegrityError):
            ClienteFactory(tenant=tenant, cpf_cnpj=client_1.cpf_cnpj)

    def test_allows_duplicate_document_different_tenants(self):
        """Should allow same document for different tenants."""
        t1 = TenantFactory()
        t2 = TenantFactory()

        c1 = ClienteFactory(tenant=t1)

        c2 = ClienteFactory(tenant=t2, cpf_cnpj=c1.cpf_cnpj)
        assert c2.pk is not None

    def test_endereco_completo(self):
        """Should format full address."""
        cliente = ClienteFactory(
            logradouro="Rua A",
            numero="10",
            complemento="Apt 1",
            bairro="Centro",
            cidade="São Paulo",
            uf="SP",
            cep="01000-000",
        )
        esperado = "Rua A, 10, Apt 1, Centro, São Paulo/SP, 01000-000"
        assert cliente.endereco_completo == esperado

    def test_documento_formatado(self):
        """Should format document based on length."""
        # PF
        c_pf = ClienteFactory(tipo_pessoa=TipoPessoa.PF, cpf_cnpj="12345678909")

        # PJ
        c_pj = ClienteFactory(tipo_pessoa=TipoPessoa.PJ, cpf_cnpj="12345678000199")

        assert len(c_pf.documento_formatado) > 11  # Should have dots/dash
        assert len(c_pj.documento_formatado) > 14
