"""
Tests for auditoria/auth_signals.py: login, logout, login_failed audit events.
Covers lines 26-29, 35-49, 55-68.
"""

from unittest.mock import patch

import pytest
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory

from caixa_nfse.auditoria.auth_signals import audit_login, audit_login_failed, audit_logout
from caixa_nfse.auditoria.models import RegistroAuditoria
from caixa_nfse.conftest import *  # noqa: F401,F403


@pytest.fixture
def rf():
    return RequestFactory()


def _make_request(rf, user=None):
    """Create a request with session support."""
    request = rf.get("/")
    request.session = SessionStore()
    request.session.create()
    if user:
        request.user = user
    return request


@pytest.mark.django_db
class TestAuditLogin:
    def test_login_creates_audit(self, rf, admin_user):
        request = _make_request(rf, admin_user)
        audit_login(sender=None, request=request, user=admin_user)
        assert RegistroAuditoria.objects.filter(
            acao="LOGIN", registro_id=str(admin_user.pk)
        ).exists()

    @patch("caixa_nfse.auditoria.models.RegistroAuditoria.registrar")
    def test_login_exception_handled(self, mock_reg, rf, admin_user):
        mock_reg.side_effect = Exception("DB error")
        request = _make_request(rf, admin_user)
        # Should not raise
        audit_login(sender=None, request=request, user=admin_user)


@pytest.mark.django_db
class TestAuditLogout:
    def test_logout_creates_audit(self, rf, admin_user):
        request = _make_request(rf, admin_user)
        audit_logout(sender=None, request=request, user=admin_user)
        assert RegistroAuditoria.objects.filter(
            acao="LOGOUT", registro_id=str(admin_user.pk)
        ).exists()

    def test_logout_no_user(self, rf):
        request = _make_request(rf)
        # Should return early without error
        audit_logout(sender=None, request=request, user=None)

    @patch("caixa_nfse.auditoria.models.RegistroAuditoria.registrar")
    def test_logout_exception_handled(self, mock_reg, rf, admin_user):
        mock_reg.side_effect = Exception("DB error")
        request = _make_request(rf, admin_user)
        # Should not raise
        audit_logout(sender=None, request=request, user=admin_user)


@pytest.mark.django_db
class TestAuditLoginFailed:
    def test_failed_login_creates_audit(self, rf):
        request = _make_request(rf)
        audit_login_failed(
            sender=None,
            credentials={"username": "hacker@test.com"},
            request=request,
        )
        assert RegistroAuditoria.objects.filter(
            acao="LOGIN",
            justificativa__contains="hacker@test.com",
        ).exists()

    def test_failed_login_unknown_user(self, rf):
        request = _make_request(rf)
        audit_login_failed(
            sender=None,
            credentials={},
            request=request,
        )
        assert RegistroAuditoria.objects.filter(
            justificativa__contains="unknown",
        ).exists()

    @patch("caixa_nfse.auditoria.models.RegistroAuditoria.registrar")
    def test_failed_login_exception_handled(self, mock_reg, rf):
        mock_reg.side_effect = Exception("DB error")
        request = _make_request(rf)
        # Should not raise
        audit_login_failed(
            sender=None,
            credentials={"username": "test@test.com"},
            request=request,
        )
