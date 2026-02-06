import pytest
from django.contrib.auth import user_logged_in, user_logged_out, user_login_failed
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

    def test_signal_user_logged_in(self):
        request = self.factory.get("/login")
        request.user = self.user

        user_logged_in.send(sender=self.user.__class__, request=request, user=self.user)

        log = RegistroAuditoria.objects.filter(acao=AcaoAuditoria.LOGIN, usuario=self.user).last()
        assert log is not None
        assert "login" in log.justificativa

    def test_signal_user_logged_out(self):
        request = self.factory.get("/logout")
        request.user = self.user

        user_logged_out.send(sender=self.user.__class__, request=request, user=self.user)

        log = RegistroAuditoria.objects.filter(acao=AcaoAuditoria.LOGOUT, usuario=self.user).last()
        assert log is not None
        assert "logout" in log.justificativa

    def test_signal_login_failed(self):
        request = self.factory.post("/login")
        credentials = {"username": "wrong_user"}

        user_login_failed.send(sender=None, credentials=credentials, request=request)

        log = RegistroAuditoria.objects.filter(acao=AcaoAuditoria.LOGIN).last()
        # Note: In failure, user might be None or not set in log model depending on implementation
        # The signal handler sets usuario=None (because request.user is likely Anon)
        assert log is not None
        assert "Falha de login" in log.justificativa
        assert "wrong_user" in log.justificativa

    def test_decorator_audit_action_success(self):

        @audit_action(acao=AcaoAuditoria.EXPORT, justificativa_template="Exported {id}")
        def dummy_view(request, id):
            return HttpResponse("OK")

        request = self.factory.get("/export/123")
        request.user = self.user
        request.tenant = self.tenant  # Middleware usually adds this

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

        request = self.factory.get("/export")
        request.user = self.user
        request.tenant = self.tenant

        # Capture current count
        count_before = RegistroAuditoria.objects.count()

        dummy_view(request)

        count_after = RegistroAuditoria.objects.count()
        assert count_after == count_before  # Should not log on 400
