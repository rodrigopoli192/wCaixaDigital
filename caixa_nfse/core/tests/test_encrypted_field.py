"""Tests for EncryptedCharField — encrypt/decrypt transparency."""

import pytest
from django.db import connection

from caixa_nfse.backoffice.models import Sistema
from caixa_nfse.core.encrypted_fields import EncryptedCharField, _get_fernet, _is_encrypted
from caixa_nfse.core.models import ConexaoExterna, Tenant


@pytest.fixture
def tenant(db):
    return Tenant.objects.create(
        razao_social="Test Corp",
        cnpj="11222333000181",
        logradouro="R",
        numero="1",
        bairro="B",
        cidade="C",
        uf="SP",
        cep="00000000",
        codigo_ibge="3550308",
    )


@pytest.fixture
def sistema(db):
    return Sistema.objects.create(nome="Test System", ativo=True)


@pytest.mark.django_db
class TestEncryptedCharField:
    def test_value_is_encrypted_in_db(self, tenant, sistema):
        """Raw DB value must be a Fernet token, not plaintext."""
        obj = ConexaoExterna.objects.create(
            tenant=tenant,
            sistema=sistema,
            tipo_conexao="MSSQL",
            host="localhost",
            porta=1433,
            database="testdb",
            usuario="sa",
            senha="SuperSecret123",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT senha FROM core_conexaoexterna WHERE host = %s AND usuario = %s",
                ["localhost", "sa"],
            )
            raw_value = cursor.fetchone()[0]

        assert raw_value != "SuperSecret123"
        assert _is_encrypted(raw_value)

    def test_value_is_decrypted_on_read(self, tenant, sistema):
        """ORM read must return the original plaintext."""
        obj = ConexaoExterna.objects.create(
            tenant=tenant,
            sistema=sistema,
            tipo_conexao="MSSQL",
            host="localhost",
            porta=1433,
            database="testdb",
            usuario="sa",
            senha="SuperSecret123",
        )
        obj.refresh_from_db()
        assert obj.senha == "SuperSecret123"

    def test_empty_string_not_encrypted(self, tenant, sistema):
        obj = ConexaoExterna.objects.create(
            tenant=tenant,
            sistema=None,
            tipo_conexao="MSSQL",
            host="localhost",
            porta=1433,
            database="testdb",
            usuario="sa",
            senha="",
        )
        obj.refresh_from_db()
        assert obj.senha == ""

    def test_no_double_encrypt(self, tenant, sistema):
        """Saving an already-encrypted value must not re-encrypt."""
        obj = ConexaoExterna.objects.create(
            tenant=tenant,
            sistema=sistema,
            tipo_conexao="MSSQL",
            host="localhost",
            porta=1433,
            database="testdb",
            usuario="sa",
            senha="MyPassword",
        )
        # Save again — must not double-encrypt
        obj.save()
        obj.refresh_from_db()
        assert obj.senha == "MyPassword"

    def test_fernet_roundtrip(self):
        """Direct Fernet encrypt/decrypt roundtrip."""
        fernet = _get_fernet()
        original = "test_password_123"
        encrypted = fernet.encrypt(original.encode()).decode()
        assert _is_encrypted(encrypted)
        decrypted = fernet.decrypt(encrypted.encode()).decode()
        assert decrypted == original

    def test_field_prep_and_from_db(self):
        """Test the field methods directly."""
        field = EncryptedCharField(max_length=500)
        prepped = field.get_prep_value("hello")
        assert prepped != "hello"
        assert _is_encrypted(prepped)

        restored = field.from_db_value(prepped, None, None)
        assert restored == "hello"

    def test_none_passthrough(self):
        field = EncryptedCharField(max_length=500)
        assert field.get_prep_value(None) is None
        assert field.from_db_value(None, None, None) is None
