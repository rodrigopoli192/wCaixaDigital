import pytest

from caixa_nfse.api.serializers import CaixaSerializer, ClienteSerializer, NotaFiscalSerializer
from caixa_nfse.tests.factories import (
    CaixaFactory,
    NotaFiscalServicoFactory,
)


@pytest.mark.django_db
class TestCaixaSerializer:
    def test_valid_data(self):
        data = {"identificador": "C01", "tipo": "FISICO", "status": "FECHADO", "ativo": True}
        serializer = CaixaSerializer(data=data)
        assert serializer.is_valid()
        assert serializer.validated_data["identificador"] == "C01"

    def test_read_only_fields(self):
        """Campos read-only não devem ser alterados."""
        cx = CaixaFactory()
        data = {
            "identificador": "C99",
            "saldo_atual": "999.00",  # Read-only
        }
        serializer = CaixaSerializer(instance=cx, data=data, partial=True)
        assert serializer.is_valid()
        # Saldo shouldn't change even if sent
        # Warning: DRF validated_data only creates validated dict.
        # save() updates fields.
        obj = serializer.save()
        assert obj.saldo_atual == cx.saldo_atual


@pytest.mark.django_db
class TestClienteSerializer:
    def test_valid_data(self):
        data = {
            "tipo_pessoa": "PF",
            "cpf_cnpj": "12345678901",
            "razao_social": "Cliente Teste",
            "email": "cliente@test.com",
            "uf": "SP",
        }
        serializer = ClienteSerializer(data=data)
        assert serializer.is_valid(), serializer.errors


@pytest.mark.django_db
class TestNotaFiscalSerializer:
    def test_serialize_data(self):
        # Ensure dates are dates
        from django.utils import timezone

        nf = NotaFiscalServicoFactory(
            data_emissao=timezone.now().date(), competencia=timezone.now().date()
        )
        serializer = NotaFiscalSerializer(instance=nf)
        data = serializer.data
        assert "cliente_nome" in data
        assert data["cliente_nome"] == nf.cliente.razao_social
