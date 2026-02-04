"""
Auditoria models - Immutable audit trail.
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from caixa_nfse.core.models import BaseModel, generate_hash


class AcaoAuditoria(models.TextChoices):
    """Tipos de ação auditada."""

    CREATE = "CREATE", _("Criação")
    UPDATE = "UPDATE", _("Alteração")
    DELETE = "DELETE", _("Exclusão")
    VIEW = "VIEW", _("Visualização")
    EXPORT = "EXPORT", _("Exportação")
    LOGIN = "LOGIN", _("Login")
    LOGOUT = "LOGOUT", _("Logout")
    APPROVE = "APPROVE", _("Aprovação")
    REJECT = "REJECT", _("Rejeição")


class RegistroAuditoria(BaseModel):
    """
    Trilha de auditoria imutável com hash encadeado.
    Armazena todas as operações críticas do sistema.
    """

    # Tenant (optional for superuser actions)
    tenant = models.ForeignKey(
        "core.Tenant",
        on_delete=models.CASCADE,
        related_name="registros_auditoria",
        verbose_name=_("empresa"),
        null=True,
        blank=True,
    )

    # Identificação do registro
    tabela = models.CharField(
        _("tabela"),
        max_length=100,
        db_index=True,
    )
    registro_id = models.CharField(
        _("ID do registro"),
        max_length=36,  # UUID
        db_index=True,
    )
    acao = models.CharField(
        _("ação"),
        max_length=20,
        choices=AcaoAuditoria.choices,
        db_index=True,
    )

    # Contexto do usuário
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="registros_auditoria",
        verbose_name=_("usuário"),
        null=True,
        blank=True,
    )
    ip_address = models.GenericIPAddressField(
        _("endereço IP"),
        null=True,
        blank=True,
    )
    user_agent = models.CharField(
        _("user agent"),
        max_length=500,
        blank=True,
    )
    session_id = models.CharField(
        _("ID da sessão"),
        max_length=100,
        blank=True,
    )

    # Dados antes e depois
    dados_antes = models.JSONField(
        _("dados antes"),
        null=True,
        blank=True,
        help_text=_("Estado do registro antes da alteração"),
    )
    dados_depois = models.JSONField(
        _("dados depois"),
        null=True,
        blank=True,
        help_text=_("Estado do registro após a alteração"),
    )
    campos_alterados = models.JSONField(
        _("campos alterados"),
        null=True,
        blank=True,
        help_text=_("Lista de campos que foram alterados"),
    )

    # Justificativa (para operações sensíveis)
    justificativa = models.TextField(
        _("justificativa"),
        blank=True,
    )

    # Integridade
    hash_registro = models.CharField(
        _("hash do registro"),
        max_length=64,
        editable=False,
        db_index=True,
    )
    hash_anterior = models.CharField(
        _("hash anterior"),
        max_length=64,
        blank=True,
        editable=False,
    )

    class Meta:
        verbose_name = _("registro de auditoria")
        verbose_name_plural = _("registros de auditoria")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "tabela", "registro_id"]),
            models.Index(fields=["tenant", "usuario", "created_at"]),
            models.Index(fields=["created_at"]),
        ]
        # Prevent modifications
        permissions = [
            ("view_audit_report", "Can view audit reports"),
            ("export_audit_log", "Can export audit logs"),
        ]

    def __str__(self):
        return f"{self.get_acao_display()} - {self.tabela} #{self.registro_id}"

    def save(self, *args, **kwargs):
        """Generate hash before saving. Record is immutable after creation."""
        if self.pk and not self._state.adding:
            raise ValueError("Registros de auditoria não podem ser alterados.")

        if not self.hash_registro:
            # Get previous hash for chain integrity
            last_record = RegistroAuditoria.objects.order_by("-created_at").first()
            self.hash_anterior = last_record.hash_registro if last_record else ""

            # Generate hash including previous hash
            data = {
                "tenant_id": str(self.tenant_id) if self.tenant_id else "",
                "tabela": self.tabela,
                "registro_id": self.registro_id,
                "acao": self.acao,
                "usuario_id": str(self.usuario_id) if self.usuario_id else "",
                "dados_antes": self.dados_antes,
                "dados_depois": self.dados_depois,
            }
            self.hash_registro = generate_hash(data, self.hash_anterior)

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Prevent deletion of audit records."""
        raise ValueError("Registros de auditoria não podem ser excluídos.")

    @classmethod
    def registrar(
        cls,
        tabela: str,
        registro_id: str,
        acao: str,
        request=None,
        dados_antes: dict = None,
        dados_depois: dict = None,
        justificativa: str = "",
    ):
        """
        Helper method to create audit record.

        Args:
            tabela: Table/model name
            registro_id: ID of the affected record
            acao: Action type (from AcaoAuditoria)
            request: HTTP request (for context)
            dados_antes: State before change
            dados_depois: State after change
            justificativa: Reason for the action

        Returns:
            RegistroAuditoria instance
        """
        tenant = None
        usuario = None
        ip_address = None
        user_agent = ""
        session_id = ""

        if request:
            if hasattr(request, "user") and request.user.is_authenticated:
                usuario = request.user
                tenant = getattr(request.user, "tenant", None)

            # Get IP from headers
            x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(",")[0].strip()
            else:
                ip_address = request.META.get("REMOTE_ADDR")

            user_agent = request.META.get("HTTP_USER_AGENT", "")[:500]
            session_id = request.session.session_key or ""

        # Calculate changed fields
        campos_alterados = None
        if dados_antes and dados_depois:
            campos_alterados = [
                k
                for k in set(dados_antes.keys()) | set(dados_depois.keys())
                if dados_antes.get(k) != dados_depois.get(k)
            ]

        return cls.objects.create(
            tenant=tenant,
            tabela=tabela,
            registro_id=str(registro_id),
            acao=acao,
            usuario=usuario,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            dados_antes=dados_antes,
            dados_depois=dados_depois,
            campos_alterados=campos_alterados,
            justificativa=justificativa,
        )

    @classmethod
    def verificar_integridade(cls, tenant=None) -> tuple[bool, list]:
        """
        Verify chain integrity of audit records.

        Returns:
            Tuple of (is_valid, list of broken records)
        """
        qs = cls.objects.all()
        if tenant:
            qs = qs.filter(tenant=tenant)

        qs = qs.order_by("created_at")

        broken_records = []
        previous_hash = ""

        for record in qs.iterator():
            expected_previous = record.hash_anterior
            if expected_previous != previous_hash:
                broken_records.append(
                    {
                        "id": str(record.id),
                        "expected": previous_hash,
                        "found": expected_previous,
                    }
                )
            previous_hash = record.hash_registro

        return len(broken_records) == 0, broken_records
