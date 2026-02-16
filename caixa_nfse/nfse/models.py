"""
NFS-e models - Nota Fiscal de Serviço Eletrônica.
"""

import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from caixa_nfse.core.encrypted_fields import EncryptedCharField
from caixa_nfse.core.models import BaseModel, Tenant, TenantAwareModel


class AmbienteNFSe(models.TextChoices):
    HOMOLOGACAO = "HOMOLOGACAO", _("Homologação")
    PRODUCAO = "PRODUCAO", _("Produção")


class BackendNFSe(models.TextChoices):
    MOCK = "mock", _("Mock (Testes)")
    PORTAL_NACIONAL = "portal_nacional", _("Portal Nacional")
    FOCUS_NFE = "focus_nfe", _("Focus NFe")
    TECNOSPEED = "tecnospeed", _("TecnoSpeed")
    PYNFE = "pynfe", _("PyNFe Híbrido")


class StatusNFSe(models.TextChoices):
    """Status da NFS-e."""

    RASCUNHO = "RASCUNHO", _("Rascunho")
    ENVIANDO = "ENVIANDO", _("Enviando")
    AUTORIZADA = "AUTORIZADA", _("Autorizada")
    REJEITADA = "REJEITADA", _("Rejeitada")
    CANCELADA = "CANCELADA", _("Cancelada")
    SUBSTITUIDA = "SUBSTITUIDA", _("Substituída")


class TipoEventoFiscal(models.TextChoices):
    """Tipo de evento fiscal."""

    GERACAO = "GERACAO", _("Geração RPS")
    ENVIO = "ENVIO", _("Envio à Prefeitura")
    AUTORIZACAO = "AUTORIZACAO", _("Autorização")
    REJEICAO = "REJEICAO", _("Rejeição")
    CONSULTA = "CONSULTA", _("Consulta")
    CANCELAMENTO = "CANCELAMENTO", _("Cancelamento")
    SUBSTITUICAO = "SUBSTITUICAO", _("Substituição")


class ServicoMunicipal(BaseModel):
    """
    Código de serviço municipal (LC 116).
    """

    codigo_lc116 = models.CharField(
        _("código LC 116"),
        max_length=10,
        db_index=True,
    )
    codigo_municipal = models.CharField(
        _("código municipal"),
        max_length=20,
        blank=True,
    )
    descricao = models.TextField(_("descrição"))
    aliquota_iss = models.DecimalField(
        _("alíquota ISS"),
        max_digits=5,
        decimal_places=4,
        default=Decimal("0.05"),
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )
    municipio_ibge = models.CharField(
        _("código IBGE município"),
        max_length=7,
        db_index=True,
    )

    class Meta:
        verbose_name = _("serviço municipal")
        verbose_name_plural = _("serviços municipais")
        ordering = ["codigo_lc116"]
        unique_together = [["codigo_lc116", "municipio_ibge"]]

    def __str__(self):
        return f"{self.codigo_lc116} - {self.descricao[:50]}"


class NotaFiscalServico(TenantAwareModel):
    """
    NFS-e - Nota Fiscal de Serviço Eletrônica.
    """

    # Idempotência
    uuid_transacao = models.UUIDField(
        _("UUID transação"),
        default=uuid.uuid4,
        editable=False,
        db_index=True,
        help_text=_("Chave de idempotência para evitar duplicidade em retries"),
    )

    # Tomador
    cliente = models.ForeignKey(
        "clientes.Cliente",
        on_delete=models.PROTECT,
        related_name="notas_fiscais",
        verbose_name=_("tomador"),
    )

    # RPS (Recibo Provisório de Serviços)
    numero_rps = models.PositiveIntegerField(
        _("número RPS"),
        db_index=True,
    )
    serie_rps = models.CharField(
        _("série RPS"),
        max_length=10,
        default="1",
    )

    # NFS-e (após autorização)
    numero_nfse = models.PositiveIntegerField(
        _("número NFS-e"),
        null=True,
        blank=True,
        db_index=True,
    )
    codigo_verificacao = models.CharField(
        _("código verificação"),
        max_length=50,
        blank=True,
    )

    # Datas
    data_emissao = models.DateField(
        _("data emissão"),
        default=timezone.now,
    )
    competencia = models.DateField(
        _("competência"),
        help_text=_("Mês/ano de competência"),
    )

    # Serviço
    servico = models.ForeignKey(
        ServicoMunicipal,
        on_delete=models.PROTECT,
        related_name="notas",
        verbose_name=_("serviço"),
    )
    discriminacao = models.TextField(
        _("discriminação do serviço"),
    )

    # Valores
    valor_servicos = models.DecimalField(
        _("valor dos serviços"),
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    valor_deducoes = models.DecimalField(
        _("valor deduções"),
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    base_calculo = models.DecimalField(
        _("base de cálculo"),
        max_digits=14,
        decimal_places=2,
        editable=False,
    )

    # Impostos PIS/COFINS/IR/CSLL/INSS
    valor_pis = models.DecimalField(
        _("valor PIS"),
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    valor_cofins = models.DecimalField(
        _("valor COFINS"),
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    valor_inss = models.DecimalField(
        _("valor INSS"),
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    valor_ir = models.DecimalField(
        _("valor IR"),
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    valor_csll = models.DecimalField(
        _("valor CSLL"),
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    # ISS
    aliquota_iss = models.DecimalField(
        _("alíquota ISS"),
        max_digits=5,
        decimal_places=4,
    )
    valor_iss = models.DecimalField(
        _("valor ISS"),
        max_digits=14,
        decimal_places=2,
        editable=False,
    )
    iss_retido = models.BooleanField(
        _("ISS retido"),
        default=False,
    )

    # Valor líquido
    valor_liquido = models.DecimalField(
        _("valor líquido"),
        max_digits=14,
        decimal_places=2,
        editable=False,
    )

    # Local de prestação
    local_prestacao_ibge = models.CharField(
        _("código IBGE local prestação"),
        max_length=7,
    )

    # Status
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=StatusNFSe.choices,
        default=StatusNFSe.RASCUNHO,
    )
    protocolo = models.CharField(
        _("protocolo"),
        max_length=100,
        blank=True,
    )

    # XMLs
    xml_rps = models.TextField(
        _("XML RPS"),
        blank=True,
        help_text=_("XML enviado à prefeitura"),
    )
    xml_nfse = models.TextField(
        _("XML NFS-e"),
        blank=True,
        help_text=_("XML retornado pela prefeitura"),
    )
    pdf_url = models.URLField(
        _("URL PDF"),
        blank=True,
    )

    # --- Campos NFS-e Nacional ---
    chave_acesso = models.CharField(
        _("chave de acesso"),
        max_length=50,
        blank=True,
        help_text=_("Chave de acesso da NFS-e Nacional (50 dígitos)"),
    )
    id_dps = models.CharField(
        _("ID DPS"),
        max_length=100,
        blank=True,
        help_text=_("Identificador da DPS no Portal Nacional"),
    )
    ambiente = models.CharField(
        _("ambiente"),
        max_length=15,
        choices=AmbienteNFSe.choices,
        default=AmbienteNFSe.HOMOLOGACAO,
    )
    backend_utilizado = models.CharField(
        _("backend utilizado"),
        max_length=20,
        choices=BackendNFSe.choices,
        blank=True,
    )
    valor_cbs = models.DecimalField(
        _("valor CBS"),
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text=_("Contribuição sobre Bens e Serviços"),
    )
    valor_ibs = models.DecimalField(
        _("valor IBS"),
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text=_("Imposto sobre Bens e Serviços"),
    )

    # Nota substituída (para substituição)
    nota_substituida = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="nota_substituta",
        verbose_name=_("nota substituída"),
        null=True,
        blank=True,
    )

    # Retorno bruto do gateway
    json_retorno_gateway = models.JSONField(
        _("retorno do gateway"),
        null=True,
        blank=True,
        help_text=_("Resposta JSON/dict bruta do gateway para auditoria"),
    )

    # Mensagem de erro rápida
    mensagem_erro = models.TextField(
        _("mensagem de erro"),
        blank=True,
        help_text=_("Última mensagem de erro/rejeição para consulta rápida"),
    )

    # Cancelamento
    motivo_cancelamento = models.TextField(
        _("motivo cancelamento"),
        blank=True,
    )
    data_cancelamento = models.DateTimeField(
        _("data cancelamento"),
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = _("nota fiscal de serviço")
        verbose_name_plural = _("notas fiscais de serviço")
        ordering = ["-data_emissao", "-numero_rps"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "numero_rps", "serie_rps"],
                name="unique_rps",
            ),
        ]

    def __str__(self):
        if self.numero_nfse:
            return f"NFS-e {self.numero_nfse}"
        return f"RPS {self.numero_rps}"

    def save(self, *args, **kwargs):
        """Calculate derived fields."""
        self.base_calculo = self.valor_servicos - self.valor_deducoes
        self.valor_iss = self.base_calculo * self.aliquota_iss

        retencoes = (
            self.valor_pis + self.valor_cofins + self.valor_inss + self.valor_ir + self.valor_csll
        )
        if self.iss_retido:
            retencoes += self.valor_iss

        self.valor_liquido = self.valor_servicos - retencoes

        super().save(*args, **kwargs)

    @property
    def pode_cancelar(self) -> bool:
        """Verifica se nota pode ser cancelada (prazo de 30 dias)."""
        if self.status != StatusNFSe.AUTORIZADA:
            return False

        from datetime import timedelta

        prazo = self.data_emissao + timedelta(days=30)
        return timezone.now().date() <= prazo


class EventoFiscal(TenantAwareModel):
    """
    Log de eventos da NFS-e.
    """

    nota = models.ForeignKey(
        NotaFiscalServico,
        on_delete=models.CASCADE,
        related_name="eventos",
        verbose_name=_("nota"),
    )
    tipo = models.CharField(
        _("tipo"),
        max_length=20,
        choices=TipoEventoFiscal.choices,
    )
    data_hora = models.DateTimeField(
        _("data/hora"),
        auto_now_add=True,
    )
    protocolo = models.CharField(
        _("protocolo"),
        max_length=100,
        blank=True,
    )
    xml_envio = models.TextField(
        _("XML envio"),
        blank=True,
    )
    xml_retorno = models.TextField(
        _("XML retorno"),
        blank=True,
    )
    mensagem = models.TextField(
        _("mensagem"),
        blank=True,
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="eventos_fiscais",
        verbose_name=_("usuário"),
        null=True,
        blank=True,
    )
    sucesso = models.BooleanField(_("sucesso"), default=True)

    class Meta:
        verbose_name = _("evento fiscal")
        verbose_name_plural = _("eventos fiscais")
        ordering = ["-data_hora"]

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.nota}"


class ConfiguracaoNFSe(TenantAwareModel):
    """
    Configuração NFS-e por tenant (1:1).
    Define backend, ambiente e comportamento de emissão.
    """

    tenant = models.OneToOneField(
        Tenant,
        on_delete=models.CASCADE,
        related_name="config_nfse",
        verbose_name=_("empresa"),
    )
    backend = models.CharField(
        _("provedor de emissão"),
        max_length=20,
        choices=BackendNFSe.choices,
        default=BackendNFSe.MOCK,
    )
    ambiente = models.CharField(
        _("ambiente"),
        max_length=15,
        choices=AmbienteNFSe.choices,
        default=AmbienteNFSe.HOMOLOGACAO,
    )
    gerar_nfse_ao_confirmar = models.BooleanField(
        _("gerar NFS-e ao confirmar pagamento"),
        default=False,
        help_text=_("Se ativo, gera NFS-e automaticamente ao confirmar movimento"),
    )

    # Credenciais gateway (Focus NFe / TecnoSpeed) — criptografadas em repouso
    api_token = EncryptedCharField(
        _("API token"),
        max_length=500,
        blank=True,
    )
    api_secret = EncryptedCharField(
        _("API secret"),
        max_length=500,
        blank=True,
    )
    webhook_token = models.CharField(
        _("token do webhook"),
        max_length=64,
        blank=True,
        db_index=True,
        help_text=_("Token para autenticação de callbacks dos gateways"),
    )

    class Meta:
        verbose_name = _("configuração NFS-e")
        verbose_name_plural = _("configurações NFS-e")

    def __str__(self):
        return f"Config NFS-e - {self.tenant} ({self.get_backend_display()})"


# Import NfseApiLog so Django discovers the model for migrations
from caixa_nfse.nfse.models_api_log import NfseApiLog  # noqa: E402, F401
