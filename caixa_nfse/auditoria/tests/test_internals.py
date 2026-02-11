import pytest
from django.http import HttpResponse
from django.test import RequestFactory

from caixa_nfse.auditoria.decorators import audit_action
from caixa_nfse.auditoria.models import AcaoAuditoria, RegistroAuditoria
from caixa_nfse.tests.factories import TenantFactory, UserFactory


@pytest.mark.django_db
class TestAuditoriaInternals:
    def setup_method(self):
        self.tenant = TenantFactory()
        self.user = UserFactory(tenant=self.tenant)
        self.factory = RequestFactory()

    def _make_request(self, path="/test"):
        request = self.factory.get(path)
        request.user = self.user
        request.tenant = self.tenant
        # RequestFactory doesn't add session — add a mock
        from unittest.mock import MagicMock

        request.session = MagicMock()
        request.session.session_key = "test-session-key"
        return request

    def test_decorator_audit_action_success(self):
        @audit_action(acao=AcaoAuditoria.EXPORT, justificativa_template="Exported {id}")
        def dummy_view(request, id):
            return HttpResponse("OK")

        request = self._make_request("/export/123")
        response = dummy_view(request, id="123")

        assert response.status_code == 200

        log = RegistroAuditoria.objects.filter(acao=AcaoAuditoria.EXPORT).last()
        assert log is not None
        assert "Exported 123" in log.justificativa
        assert log.usuario == self.user

    def test_decorator_audit_action_fail_status(self):
        @audit_action(acao=AcaoAuditoria.EXPORT)
        def dummy_view(request):
            return HttpResponse("Error", status=400)

        request = self._make_request("/export")
        count_before = RegistroAuditoria.objects.count()

        dummy_view(request)

        count_after = RegistroAuditoria.objects.count()
        assert count_after == count_before  # Should not log on 400

    def test_registrar_creates_record(self):
        record = RegistroAuditoria.registrar(
            tabela="test_table", registro_id="123", acao="CREATE", dados_depois={"foo": "bar"}
        )
        assert record.pk is not None
        assert record.tabela == "test_table"
        assert record.hash_registro is not None

    def test_registrar_with_request(self):
        request = self._make_request()
        request.META["HTTP_X_FORWARDED_FOR"] = "10.0.0.1"
        request.META["HTTP_USER_AGENT"] = "TestAgent"

        record = RegistroAuditoria.registrar(
            tabela="x", registro_id="1", acao="VIEW", request=request
        )
        assert record.usuario == self.user
        assert record.ip_address == "10.0.0.1"
        assert record.user_agent == "TestAgent"

    def test_model_to_dict_from_signals(self):
        from caixa_nfse.auditoria.signals import model_to_dict, should_audit
        from caixa_nfse.caixa.models import Caixa

        assert should_audit(Caixa) is True
        assert should_audit(RegistroAuditoria) is False

        caixa = Caixa(identificador="TEST", tenant=self.tenant)
        data = model_to_dict(caixa)
        assert "identificador" in data
        assert data["identificador"] == "TEST"
