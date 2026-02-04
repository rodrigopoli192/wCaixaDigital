"""
Contabil models - Accounting ledger.
"""

from decimal import Decimal

from django.db import models
from django.utils.translation import gettext_lazy as _

from caixa_nfse.core.models import BaseModel, TenantAwareModel


class TipoConta(models.TextChoices):
    ATIVO = "ATIVO", _("Ativo")
    PASSIVO = "PASSIVO", _("Passivo")
    RECEITA = "RECEITA", _("Receita")
    DESPESA = "DESPESA", _("Despesa")
    RESULTADO = "RESULTADO", _("Resultado")


class NaturezaConta(models.TextChoices):
    DEVEDORA = "D", _("Devedora")
    CREDORA = "C", _("Credora")


class TipoPartida(models.TextChoices):
    DEBITO = "D", _("Débito")
    CREDITO = "C", _("Crédito")


class PlanoContas(TenantAwareModel):
    """Plano de contas hierárquico."""

    codigo = models.CharField(_("código"), max_length=20, db_index=True)
    descricao = models.CharField(_("descrição"), max_length=200)
    tipo = models.CharField(_("tipo"), max_length=20, choices=TipoConta.choices)
    natureza = models.CharField(_("natureza"), max_length=1, choices=NaturezaConta.choices)
    nivel = models.PositiveSmallIntegerField(_("nível"), default=1)
    conta_pai = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="subcontas",
        null=True,
        blank=True,
    )
    permite_lancamento = models.BooleanField(_("permite lançamento"), default=True)
    ativo = models.BooleanField(_("ativo"), default=True)

    class Meta:
        verbose_name = _("plano de contas")
        verbose_name_plural = _("planos de contas")
        ordering = ["codigo"]
        unique_together = [["tenant", "codigo"]]

    def __str__(self):
        return f"{self.codigo} - {self.descricao}"


class CentroCusto(TenantAwareModel):
    """Centro de custo para rateio."""

    codigo = models.CharField(_("código"), max_length=20)
    descricao = models.CharField(_("descrição"), max_length=200)
    ativo = models.BooleanField(_("ativo"), default=True)

    class Meta:
        verbose_name = _("centro de custo")
        verbose_name_plural = _("centros de custo")
        ordering = ["codigo"]
        unique_together = [["tenant", "codigo"]]

    def __str__(self):
        return f"{self.codigo} - {self.descricao}"


class LancamentoContabil(TenantAwareModel):
    """Lançamento contábil (cabeçalho)."""

    data_lancamento = models.DateField(_("data lançamento"), db_index=True)
    data_competencia = models.DateField(_("competência"), db_index=True)
    numero_documento = models.CharField(_("nº documento"), max_length=50, blank=True)
    historico = models.TextField(_("histórico"))

    # Origem
    origem_tipo = models.CharField(
        _("tipo origem"),
        max_length=50,
        blank=True,
        help_text=_("movimento_caixa, nota_fiscal, ajuste"),
    )
    origem_id = models.CharField(_("ID origem"), max_length=36, blank=True)

    # Estorno
    estornado = models.BooleanField(_("estornado"), default=False)
    lancamento_estorno = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="estorno_de",
        null=True,
        blank=True,
    )

    valor_total = models.DecimalField(
        _("valor total"),
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    class Meta:
        verbose_name = _("lançamento contábil")
        verbose_name_plural = _("lançamentos contábeis")
        ordering = ["-data_lancamento", "-created_at"]

    def __str__(self):
        return f"Lançamento {self.data_lancamento} - {self.historico[:30]}"


class PartidaLancamento(BaseModel):
    """Partidas do lançamento (débitos e créditos)."""

    lancamento = models.ForeignKey(
        LancamentoContabil,
        on_delete=models.CASCADE,
        related_name="partidas",
    )
    conta = models.ForeignKey(
        PlanoContas,
        on_delete=models.PROTECT,
        related_name="partidas",
    )
    centro_custo = models.ForeignKey(
        CentroCusto,
        on_delete=models.SET_NULL,
        related_name="partidas",
        null=True,
        blank=True,
    )
    tipo = models.CharField(_("tipo"), max_length=1, choices=TipoPartida.choices)
    valor = models.DecimalField(_("valor"), max_digits=14, decimal_places=2)
    historico_complementar = models.CharField(_("complemento"), max_length=200, blank=True)

    class Meta:
        verbose_name = _("partida")
        verbose_name_plural = _("partidas")

    def __str__(self):
        return f"{self.get_tipo_display()} {self.conta.codigo} R$ {self.valor}"
