import pytest

from caixa_nfse.auditoria.models import RegistroAuditoria
from caixa_nfse.tests.factories import RegistroAuditoriaFactory, TenantFactory


@pytest.mark.django_db
class TestRegistroAuditoriaModel:
    """Tests for RegistroAuditoria model."""

    def test_create_generates_hash(self):
        record = RegistroAuditoriaFactory()
        assert record.hash_registro is not None
        assert len(record.hash_registro) == 64

    def test_chaining_same_tenant(self):
        """Hash chaining works via direct registrar (avoids signal interference)."""
        r1 = RegistroAuditoria.registrar(
            tabela="test", registro_id="1", acao="CREATE", dados_depois={"a": 1}
        )
        r2 = RegistroAuditoria.registrar(
            tabela="test", registro_id="2", acao="CREATE", dados_depois={"b": 2}
        )
        assert r2.hash_anterior == r1.hash_registro
        assert r1.hash_registro != r2.hash_registro

    def test_immutability_update(self):
        record = RegistroAuditoriaFactory()
        record.acao = "UPDATE"
        with pytest.raises(ValueError, match="não podem ser alterados"):
            record.save()

    def test_immutability_delete(self):
        record = RegistroAuditoriaFactory()
        with pytest.raises(ValueError, match="não podem ser excluídos"):
            record.delete()

    def test_registrar_helper(self):
        record = RegistroAuditoria.registrar(
            tabela="test_table", registro_id="123", acao="CREATE", dados_depois={"foo": "bar"}
        )
        assert record.pk is not None
        assert record.tabela == "test_table"
        assert record.hash_registro is not None

    def test_registrar_with_request(self):
        from unittest.mock import MagicMock

        from django.test import RequestFactory

        user = RegistroAuditoriaFactory.create().usuario
        factory = RequestFactory()
        request = factory.get("/")
        request.user = user
        request.META["HTTP_X_FORWARDED_FOR"] = "10.0.0.1"
        request.META["HTTP_USER_AGENT"] = "TestAgent"
        request.session = MagicMock()
        request.session.session_key = "sess-key"

        record = RegistroAuditoria.registrar(
            tabela="x", registro_id="1", acao="VIEW", request=request
        )
        assert record.usuario == request.user
        assert record.ip_address == "10.0.0.1"
        assert record.user_agent == "TestAgent"

    def test_integridade_ok(self):
        # Verify global integrity — all audit records should be chained
        valid, broken = RegistroAuditoria.verificar_integridade()
        assert valid is True
        assert len(broken) == 0

    def test_integridade_broken(self):
        t = TenantFactory()
        r1 = RegistroAuditoriaFactory(tenant=t)
        RegistroAuditoriaFactory(tenant=t)

        # Tamper with r1 hash using queryset update to bypass save() check
        RegistroAuditoria.objects.filter(pk=r1.pk).update(hash_registro="TAMPERED_HASH")

        valid, broken = RegistroAuditoria.verificar_integridade()
        assert valid is False
        assert len(broken) > 0
