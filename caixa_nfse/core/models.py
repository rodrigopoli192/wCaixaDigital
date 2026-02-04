"""
Core models - Base classes and shared models.
"""

import hashlib
import uuid
from typing import Any

from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class BaseModel(models.Model):
    """
    Abstract base model with common fields.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    created_at = models.DateTimeField(
        _("criado em"),
        auto_now_add=True,
        db_index=True,
    )
    updated_at = models.DateTimeField(
        _("atualizado em"),
        auto_now=True,
    )

    class Meta:
        abstract = True
        ordering = ["-created_at"]


class BaseAuditModel(BaseModel):
    """
    Abstract model with audit fields for tracking changes.
    """

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="%(class)s_created",
        verbose_name=_("criado por"),
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="%(class)s_updated",
        verbose_name=_("atualizado por"),
        null=True,
        blank=True,
    )

    class Meta:
        abstract = True


class TenantManager(models.Manager):
    """Manager for Tenant with active filter."""

    def get_queryset(self):
        return super().get_queryset().filter(ativo=True)

    def all_with_inactive(self):
        return super().get_queryset()


class RegimeTributario(models.TextChoices):
    """Regime tributário da empresa."""

    SIMPLES = "SIMPLES", _("Simples Nacional")
    LUCRO_PRESUMIDO = "PRESUMIDO", _("Lucro Presumido")
    LUCRO_REAL = "REAL", _("Lucro Real")
    MEI = "MEI", _("Microempreendedor Individual")


class Tenant(BaseModel):
    """
    Empresa/Estabelecimento - Multi-tenant isolation.
    """

    # Identificação
    razao_social = models.CharField(
        _("razão social"),
        max_length=255,
    )
    nome_fantasia = models.CharField(
        _("nome fantasia"),
        max_length=255,
        blank=True,
    )
    cnpj = models.CharField(
        _("CNPJ"),
        max_length=18,
        unique=True,
        help_text=_("Formato: 00.000.000/0000-00"),
    )

    # Inscrições
    inscricao_municipal = models.CharField(
        _("inscrição municipal"),
        max_length=50,
        blank=True,
    )
    inscricao_estadual = models.CharField(
        _("inscrição estadual"),
        max_length=50,
        blank=True,
    )

    # Regime tributário
    regime_tributario = models.CharField(
        _("regime tributário"),
        max_length=20,
        choices=RegimeTributario.choices,
        default=RegimeTributario.SIMPLES,
    )

    # Endereço
    logradouro = models.CharField(_("logradouro"), max_length=255)
    numero = models.CharField(_("número"), max_length=20)
    complemento = models.CharField(_("complemento"), max_length=100, blank=True)
    bairro = models.CharField(_("bairro"), max_length=100)
    cidade = models.CharField(_("cidade"), max_length=100)
    uf = models.CharField(_("UF"), max_length=2)
    cep = models.CharField(_("CEP"), max_length=9)
    codigo_ibge = models.CharField(
        _("código IBGE"),
        max_length=7,
        help_text=_("Código IBGE do município"),
    )

    # Contato
    telefone = models.CharField(_("telefone"), max_length=20, blank=True)
    email = models.EmailField(_("e-mail"), blank=True)

    # Certificado Digital
    certificado_digital = models.BinaryField(
        _("certificado digital"),
        null=True,
        blank=True,
        help_text=_("Arquivo .pfx do certificado A1"),
    )
    certificado_senha = models.CharField(
        _("senha do certificado"),
        max_length=255,
        blank=True,
        help_text=_("Senha criptografada"),
    )
    certificado_validade = models.DateField(
        _("validade do certificado"),
        null=True,
        blank=True,
    )

    # Configurações NFS-e
    nfse_serie_padrao = models.CharField(
        _("série NFS-e padrão"),
        max_length=10,
        default="1",
    )
    nfse_ultimo_rps = models.PositiveIntegerField(
        _("último RPS"),
        default=0,
    )

    # Status
    ativo = models.BooleanField(_("ativo"), default=True)

    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        verbose_name = _("empresa")
        verbose_name_plural = _("empresas")
        ordering = ["razao_social"]

    def __str__(self):
        return f"{self.razao_social} ({self.cnpj})"

    @property
    def endereco_completo(self) -> str:
        """Retorna endereço formatado."""
        partes = [
            self.logradouro,
            self.numero,
            self.complemento,
            self.bairro,
            f"{self.cidade}/{self.uf}",
            self.cep,
        ]
        return ", ".join(p for p in partes if p)

    @property
    def certificado_valido(self) -> bool:
        """Verifica se o certificado ainda é válido."""
        if not self.certificado_validade:
            return False
        return self.certificado_validade > timezone.now().date()

    def proximo_numero_rps(self) -> int:
        """Retorna e incrementa o próximo número de RPS."""
        self.nfse_ultimo_rps += 1
        self.save(update_fields=["nfse_ultimo_rps"])
        return self.nfse_ultimo_rps


class TenantAwareModel(BaseAuditModel):
    """
    Abstract model with tenant isolation.
    All tenant-specific models should inherit from this.
    """

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="%(class)s_set",
        verbose_name=_("empresa"),
    )

    class Meta:
        abstract = True


class UserManager(BaseUserManager):
    """Custom user manager."""

    def create_user(self, email, password=None, **extra_fields):
        """Create and return a regular user."""
        if not email:
            raise ValueError(_("O e-mail é obrigatório"))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Create and return a superuser."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Superuser deve ter is_staff=True."))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Superuser deve ter is_superuser=True."))

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    Custom User model with email as username.
    """

    username = None  # Remove username field
    email = models.EmailField(_("e-mail"), unique=True)

    # Tenant association (can be null for superusers)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="usuarios",
        verbose_name=_("empresa"),
        null=True,
        blank=True,
    )

    # Profile
    cpf = models.CharField(
        _("CPF"),
        max_length=14,
        blank=True,
        help_text=_("Formato: 000.000.000-00"),
    )
    telefone = models.CharField(
        _("telefone"),
        max_length=20,
        blank=True,
    )
    cargo = models.CharField(
        _("cargo"),
        max_length=100,
        blank=True,
    )

    # Permissions
    pode_operar_caixa = models.BooleanField(
        _("pode operar caixa"),
        default=False,
    )
    pode_emitir_nfse = models.BooleanField(
        _("pode emitir NFS-e"),
        default=False,
    )
    pode_cancelar_nfse = models.BooleanField(
        _("pode cancelar NFS-e"),
        default=False,
    )
    pode_aprovar_fechamento = models.BooleanField(
        _("pode aprovar fechamento"),
        default=False,
    )
    pode_exportar_dados = models.BooleanField(
        _("pode exportar dados"),
        default=False,
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = UserManager()

    class Meta:
        verbose_name = _("usuário")
        verbose_name_plural = _("usuários")
        ordering = ["first_name", "last_name"]

    def __str__(self):
        return self.get_full_name() or self.email

    def get_full_name(self):
        """Return first_name plus last_name."""
        return f"{self.first_name} {self.last_name}".strip()


class FormaPagamento(TenantAwareModel):
    """
    Formas de pagamento aceitas.
    """

    class TipoPagamento(models.TextChoices):
        DINHEIRO = "DINHEIRO", _("Dinheiro")
        PIX = "PIX", _("PIX")
        DEBITO = "DEBITO", _("Cartão de Débito")
        CREDITO = "CREDITO", _("Cartão de Crédito")
        BOLETO = "BOLETO", _("Boleto")
        TRANSFERENCIA = "TRANSFERENCIA", _("Transferência")
        CHEQUE = "CHEQUE", _("Cheque")
        OUTROS = "OUTROS", _("Outros")

    nome = models.CharField(_("nome"), max_length=100)
    tipo = models.CharField(
        _("tipo"),
        max_length=20,
        choices=TipoPagamento.choices,
    )
    taxa_percentual = models.DecimalField(
        _("taxa percentual"),
        max_digits=5,
        decimal_places=4,
        default=0,
        help_text=_("Taxa cobrada pela operadora (ex: 0.0199 = 1.99%)"),
    )
    prazo_recebimento = models.PositiveIntegerField(
        _("prazo recebimento (dias)"),
        default=0,
        help_text=_("Dias para recebimento após a venda"),
    )
    ativo = models.BooleanField(_("ativo"), default=True)

    # Configuração contábil
    conta_contabil = models.CharField(
        _("conta contábil"),
        max_length=20,
        blank=True,
        help_text=_("Código da conta para lançamento"),
    )

    class Meta:
        verbose_name = _("forma de pagamento")
        verbose_name_plural = _("formas de pagamento")
        ordering = ["nome"]
        unique_together = [["tenant", "nome"]]

    def __str__(self):
        return f"{self.nome} ({self.get_tipo_display()})"


def generate_hash(data: dict[str, Any], previous_hash: str = "") -> str:
    """
    Generate SHA-256 hash for audit trail.

    Args:
        data: Dictionary with data to hash
        previous_hash: Hash of previous record for chain integrity

    Returns:
        SHA-256 hash string
    """
    import json

    content = json.dumps(data, sort_keys=True, default=str)
    content = f"{previous_hash}{content}"
    return hashlib.sha256(content.encode()).hexdigest()
