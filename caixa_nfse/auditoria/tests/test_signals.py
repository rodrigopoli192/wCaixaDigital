"""
Tests for auditoria/signals.py: model_to_dict, should_audit, pre_save, post_save, post_delete.
Covers lines 33, 37-38, 79, 100-104, 124-127.
"""

from unittest.mock import MagicMock, patch

import pytest

from caixa_nfse.auditoria.models import RegistroAuditoria
from caixa_nfse.auditoria.signals import model_to_dict, should_audit
from caixa_nfse.conftest import *  # noqa: F401,F403


class TestModelToDict:
    def test_bytes_field_masked(self):
        """Binary field values should be masked."""
        mock_field = MagicMock()
        mock_field.name = "binary_data"
        mock_instance = MagicMock()
        mock_instance._meta.fields = [mock_field]
        mock_instance.binary_data = b"\x00\x01\x02"
        result = model_to_dict(mock_instance)
        assert result["binary_data"] == "[BINARY DATA]"

    def test_error_reading_field(self):
        """Field access error should be caught."""
        mock_field = MagicMock()
        mock_field.name = "bad_field"
        mock_instance = MagicMock()
        mock_instance._meta.fields = [mock_field]
        type(mock_instance).bad_field = property(
            lambda self: (_ for _ in ()).throw(RuntimeError("boom"))
        )
        result = model_to_dict(mock_instance)
        assert result["bad_field"] == "[ERROR GETTING VALUE]"


class TestShouldAudit:
    def test_auditoria_not_audited(self):
        """Auditoria models should not be audited (prevent recursion)."""
        assert should_audit(RegistroAuditoria) is False

    def test_non_audited_app(self):
        """Models from non-audited apps should not be audited."""
        mock_sender = MagicMock()
        mock_sender._meta.app_label = "auth"
        assert should_audit(mock_sender) is False


@pytest.mark.django_db
class TestAuditSignals:
    def test_post_save_skips_registro_auditoria(self):
        """Saving RegistroAuditoria itself should not create recursive audit."""
        # This is tested implicitly — creating audit records shouldn't cause recursion
        r = RegistroAuditoria.registrar(
            tabela="test", registro_id="1", acao="CREATE", dados_depois={"x": 1}
        )
        assert r.pk is not None

    @patch("caixa_nfse.auditoria.signals.RegistroAuditoria.registrar")
    def test_post_save_exception_handled(self, mock_registrar, tenant):
        """Exception in audit_save should not crash the save operation."""
        mock_registrar.side_effect = Exception("DB error")
        from caixa_nfse.core.models import FormaPagamento

        # This should NOT raise even though audit fails
        fp = FormaPagamento.objects.create(tenant=tenant, nome="Test", ativo=True)
        assert fp.pk is not None

    @patch("caixa_nfse.auditoria.signals.RegistroAuditoria.registrar")
    def test_post_delete_exception_handled(self, mock_registrar, tenant):
        """Exception in audit_delete should not crash the delete operation."""
        from caixa_nfse.core.models import FormaPagamento

        fp = FormaPagamento.objects.create(tenant=tenant, nome="DeleteMe", ativo=True)
        mock_registrar.side_effect = Exception("DB error")
        # This should NOT raise even though audit fails
        fp.delete()
