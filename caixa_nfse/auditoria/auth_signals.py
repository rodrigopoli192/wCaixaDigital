"""
Auditoria signals for authentication events.
"""

from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.dispatch import receiver

from .models import AcaoAuditoria, RegistroAuditoria


@receiver(user_logged_in)
def audit_login(sender, request, user, **kwargs):
    """Log user login."""
    try:
        RegistroAuditoria.registrar(
            tabela="auth.User",
            registro_id=str(user.pk),
            acao=AcaoAuditoria.LOGIN,
            request=request,
            justificativa="Usuário realizou login",
        )
    except Exception:
        import logging

        logging.getLogger(__name__).exception("Failed to audit login")


@receiver(user_logged_out)
def audit_logout(sender, request, user, **kwargs):
    """Log user logout."""
    if not user:
        return

    try:
        RegistroAuditoria.registrar(
            tabela="auth.User",
            registro_id=str(user.pk),
            acao=AcaoAuditoria.LOGOUT,
            request=request,
            justificativa="Usuário realizou logout",
        )
    except Exception:
        import logging

        logging.getLogger(__name__).exception("Failed to audit logout")


@receiver(user_login_failed)
def audit_login_failed(sender, credentials, request, **kwargs):
    """Log failed login attempt."""
    try:
        username = credentials.get("username", "unknown")
        RegistroAuditoria.registrar(
            tabela="auth.User",
            registro_id="0",
            acao=AcaoAuditoria.LOGIN,  # Usar LOGIN mas com justificativa de falha
            request=request,
            justificativa=f"Falha de login para usuário: {username}",
            dados_antes={"credentials": {"username": username}},  # Não logar senha!
        )
    except Exception:
        import logging

        logging.getLogger(__name__).exception("Failed to audit login failure")
