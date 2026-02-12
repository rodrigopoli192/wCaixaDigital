"""
NfseApiLog — Rastreabilidade completa de chamadas HTTP a gateways NFS-e.

Cada request/response é registrado com headers sanitizados, timing e UUID
para correlação. Registros são imutáveis (sem update/delete).
"""

import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _

from caixa_nfse.core.models import TenantAwareModel


class NfseApiLog(TenantAwareModel):
    """
    Log imutável de chamadas HTTP a APIs de gateways NFS-e.
    Garante rastreabilidade completa para auditoria fiscal.
    """

    nota = models.ForeignKey(
        "nfse.NotaFiscalServico",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="api_logs",
        verbose_name=_("nota fiscal"),
    )
    backend = models.CharField(
        _("backend"),
        max_length=20,
        db_index=True,
    )

    # ── Request ──────────────────────────────────────────────
    metodo = models.CharField(
        _("método HTTP"),
        max_length=10,
    )
    url = models.CharField(
        _("URL"),
        max_length=500,
    )
    headers_envio = models.JSONField(
        _("headers enviados"),
        default=dict,
        help_text=_("Headers sanitizados — sem tokens ou senhas"),
    )
    body_envio = models.TextField(
        _("body enviado"),
        blank=True,
    )

    # ── Response ─────────────────────────────────────────────
    status_code = models.IntegerField(
        _("status code"),
        null=True,
        blank=True,
    )
    headers_retorno = models.JSONField(
        _("headers recebidos"),
        null=True,
        blank=True,
    )
    body_retorno = models.TextField(
        _("body recebido"),
        blank=True,
    )

    # ── Timing ───────────────────────────────────────────────
    data_hora = models.DateTimeField(
        _("data/hora"),
        auto_now_add=True,
        db_index=True,
    )
    duracao_ms = models.IntegerField(
        _("duração (ms)"),
        null=True,
        blank=True,
    )

    # ── Result ───────────────────────────────────────────────
    sucesso = models.BooleanField(
        _("sucesso"),
        default=False,
    )
    erro = models.TextField(
        _("erro"),
        blank=True,
    )

    # ── Correlação ───────────────────────────────────────────
    request_id = models.UUIDField(
        _("request ID"),
        default=uuid.uuid4,
        editable=False,
        db_index=True,
    )

    class Meta:
        verbose_name = _("log de API NFS-e")
        verbose_name_plural = _("logs de API NFS-e")
        ordering = ["-data_hora"]
        indexes = [
            models.Index(fields=["tenant", "data_hora"]),
            models.Index(fields=["nota"]),
            models.Index(fields=["backend", "data_hora"]),
        ]

    def __str__(self):
        status = self.status_code or "ERR"
        return f"[{self.backend}] {self.metodo} {status} ({self.duracao_ms}ms)"

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            raise ValueError("Logs de API NFS-e são imutáveis.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Logs de API NFS-e não podem ser excluídos.")

    # ── Headers sanitization ─────────────────────────────────
    SENSITIVE_HEADERS = frozenset(
        {
            "authorization",
            "token_sh",
            "x-api-key",
            "cookie",
            "set-cookie",
        }
    )

    @classmethod
    def sanitize_headers(cls, headers: dict) -> dict:
        """Remove sensitive values from headers dict."""
        sanitized = {}
        for key, value in headers.items():
            if key.lower() in cls.SENSITIVE_HEADERS:
                sanitized[key] = "***REDACTED***"
            else:
                sanitized[key] = value
        return sanitized
