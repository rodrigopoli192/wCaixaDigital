import pytest

from caixa_nfse.auditoria.models import RegistroAuditoria
from caixa_nfse.tests.factories import RegistroAuditoriaFactory, TenantFactory


@pytest.mark.django_db
class TestRegistroAuditoriaModel:
    """Tests for RegistroAuditoria model."""

    def test_create_generates_hash(self):
        """Should generate hash on creation."""
        record = RegistroAuditoriaFactory()
        assert record.hash_registro is not None
        assert len(record.hash_registro) == 64  # SHA-256 hex digest length

    def test_chaining(self):
        """Should chain hashes."""
        r1 = RegistroAuditoriaFactory()
        r2 = RegistroAuditoriaFactory()

        # r2.hash_anterior should equal r1.hash_registro
        assert r2.hash_anterior == r1.hash_registro

    def test_immutability_update(self):
        """Should prevent updates."""
        record = RegistroAuditoriaFactory()
        record.acoes = "UPDATE"
        with pytest.raises(ValueError, match="não podem ser alterados"):
            record.save()

    def test_immutability_delete(self):
        """Should prevent deletion."""
        record = RegistroAuditoriaFactory()
        with pytest.raises(ValueError, match="não podem ser excluídos"):
            record.delete()

    def test_registrar_helper(self):
        """Should create record via helper."""
        record = RegistroAuditoria.registrar(
            tabela="test_table", registro_id="123", acao="CREATE", dados_depois={"foo": "bar"}
        )
        assert record.pk is not None
        assert record.tabela == "test_table"
        assert record.hash_registro is not None

    def test_registrar_with_request(self):
        """Should extract info from request."""
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get("/")
        request.user = self.user = RegistroAuditoriaFactory.create().usuario  # simple user
        request.META["HTTP_X_FORWARDED_FOR"] = "10.0.0.1"
        request.META["HTTP_USER_AGENT"] = "TestAgent"

        record = RegistroAuditoria.registrar(
            tabela="x", registro_id="1", acao="VIEW", request=request
        )
        assert record.usuario == request.user
        assert record.ip_address == "10.0.0.1"
        assert record.user_agent == "TestAgent"

    def test_integridade_tenant_filter(self):
        """Should filter verification by tenant."""
        t1 = TenantFactory()
        t2 = TenantFactory()

        RegistroAuditoriaFactory(tenant=t1)
        RegistroAuditoriaFactory(tenant=t2)

        valid, _ = RegistroAuditoria.verificar_integridade(tenant=t1)
        assert valid is True

    def test_integridade_ok(self):
        """Should verify integrity as valid."""
        RegistroAuditoriaFactory()
        RegistroAuditoriaFactory()

        valid, broken = RegistroAuditoria.verificar_integridade()
        assert valid is True
        assert len(broken) == 0

    def test_integridade_broken(self):
        """Should detect broken chain."""
        r1 = RegistroAuditoriaFactory()
        r1 = RegistroAuditoriaFactory()
        r2 = RegistroAuditoriaFactory()
        assert r2.hash_anterior == r1.hash_registro

        # Tamper with r1 hash using queryset update to bypass save() check
        RegistroAuditoria.objects.filter(pk=r1.pk).update(hash_registro="TAMPERED_HASH")

        # Now r2.hash_anterior (which matched old r1 hash) does NOT match new r1.hash_registro
        # Wait, verify logic:
        # Loop order by created_at.
        # Iteration 1 (r1): expected_previous="" (first). stored r1.hash_anterior="" -> OK. previous_hash becomes "TAMPERED_HASH".
        # Iteration 2 (r2): expected_previous=r2.hash_anterior (which is REAL HASH of r1). previous_hash="TAMPERED_HASH".
        # Mismatch!

        valid, broken = RegistroAuditoria.verificar_integridade()
        assert valid is False
        assert len(broken) > 0
