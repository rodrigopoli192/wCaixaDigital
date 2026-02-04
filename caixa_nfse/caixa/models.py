"""
Caixa models - Cash register operations.
"""

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from caixa_nfse.core.models import TenantAwareModel, generate_hash


class TipoCaixa(models.TextChoices):
    """Tipo de caixa."""

    FISICO = "FISICO", _("Caixa Físico")
    VIRTUAL = "VIRTUAL", _("Caixa Virtual")


class StatusCaixa(models.TextChoices):
    """Status do caixa."""

    FECHADO = "FECHADO", _("Fechado")
    ABERTO = "ABERTO", _("Aberto")
    BLOQUEADO = "BLOQUEADO", _("Bloqueado")


class TipoMovimento(models.TextChoices):
    """Tipo de movimento de caixa."""

    ENTRADA = "ENTRADA", _("Entrada")
    SAIDA = "SAIDA", _("Saída")
    SANGRIA = "SANGRIA", _("Sangria")
    SUPRIMENTO = "SUPRIMENTO", _("Suprimento")
    ESTORNO = "ESTORNO", _("Estorno")


class StatusFechamento(models.TextChoices):
    """Status do fechamento de caixa."""

    PENDENTE = "PENDENTE", _("Pendente de Aprovação")
    APROVADO = "APROVADO", _("Aprovado")
    REJEITADO = "REJEITADO", _("Rejeitado")


class Caixa(TenantAwareModel):
    """
    Representa um caixa físico ou virtual.
    """

    identificador = models.CharField(
        _("identificador"),
        max_length=50,
        help_text=_("Ex: CAIXA-01, PDV-LOJA"),
    )
    tipo = models.CharField(
        _("tipo"),
        max_length=20,
        choices=TipoCaixa.choices,
        default=TipoCaixa.FISICO,
    )
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=StatusCaixa.choices,
        default=StatusCaixa.FECHADO,
    )
    operador_atual = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="caixas_operando",
        verbose_name=_("operador atual"),
        null=True,
        blank=True,
    )
    saldo_atual = models.DecimalField(
        _("saldo atual"),
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    ativo = models.BooleanField(_("ativo"), default=True)

    class Meta:
        verbose_name = _("caixa")
        verbose_name_plural = _("caixas")
        ordering = ["identificador"]
        unique_together = [["tenant", "identificador"]]

    def __str__(self):
        return f"{self.identificador} ({self.get_status_display()})"

    def get_absolute_url(self):
        from django.urls import reverse

        return reverse("caixa:detail", kwargs={"pk": self.pk})

    @property
    def esta_aberto(self) -> bool:
        """Verifica se o caixa está aberto."""
        return self.status == StatusCaixa.ABERTO


class AberturaCaixa(TenantAwareModel):
    """
    Registro de abertura de caixa com trilha de auditoria.
    """

    caixa = models.ForeignKey(
        Caixa,
        on_delete=models.PROTECT,
        related_name="aberturas",
        verbose_name=_("caixa"),
    )
    operador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="aberturas_caixa",
        verbose_name=_("operador"),
    )
    data_hora = models.DateTimeField(
        _("data/hora abertura"),
        default=timezone.now,
    )
    saldo_abertura = models.DecimalField(
        _("saldo na abertura"),
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    fundo_troco = models.DecimalField(
        _("fundo de troco"),
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    observacao = models.TextField(
        _("observação"),
        blank=True,
    )

    # Auditoria imutável
    hash_registro = models.CharField(
        _("hash do registro"),
        max_length=64,
        editable=False,
    )
    hash_anterior = models.CharField(
        _("hash anterior"),
        max_length=64,
        blank=True,
        editable=False,
    )

    # Status
    fechado = models.BooleanField(_("fechado"), default=False)

    class Meta:
        verbose_name = _("abertura de caixa")
        verbose_name_plural = _("aberturas de caixa")
        ordering = ["-data_hora"]

    def __str__(self):
        return f"Abertura {self.caixa.identificador} - {self.data_hora.strftime('%d/%m/%Y %H:%M')}"

    def save(self, *args, **kwargs):
        """Generate hash before saving."""
        if not self.hash_registro:
            # Get previous hash
            last_abertura = (
                AberturaCaixa.objects.filter(tenant=self.tenant).order_by("-created_at").first()
            )

            self.hash_anterior = last_abertura.hash_registro if last_abertura else ""

            # Generate hash
            data = {
                "caixa_id": str(self.caixa_id),
                "operador_id": str(self.operador_id),
                "data_hora": str(self.data_hora),
                "saldo_abertura": str(self.saldo_abertura),
                "fundo_troco": str(self.fundo_troco),
            }
            self.hash_registro = generate_hash(data, self.hash_anterior)

        super().save(*args, **kwargs)

    @property
    def saldo_movimentos(self) -> Decimal:
        """Calcula saldo baseado nos movimentos."""
        entradas = self.movimentos.filter(
            tipo__in=[TipoMovimento.ENTRADA, TipoMovimento.SUPRIMENTO]
        ).aggregate(total=models.Sum("valor"))["total"] or Decimal("0.00")

        saidas = self.movimentos.filter(
            tipo__in=[TipoMovimento.SAIDA, TipoMovimento.SANGRIA, TipoMovimento.ESTORNO]
        ).aggregate(total=models.Sum("valor"))["total"] or Decimal("0.00")

        return self.saldo_abertura + entradas - saidas

    @property
    def total_entradas(self) -> Decimal:
        """Calcula total de entradas."""
        return self.movimentos.filter(
            tipo__in=[TipoMovimento.ENTRADA, TipoMovimento.SUPRIMENTO]
        ).aggregate(total=models.Sum("valor"))["total"] or Decimal("0.00")

    @property
    def total_saidas(self) -> Decimal:
        """Calcula total de saídas."""
        return self.movimentos.filter(
            tipo__in=[TipoMovimento.SAIDA, TipoMovimento.SANGRIA, TipoMovimento.ESTORNO]
        ).aggregate(total=models.Sum("valor"))["total"] or Decimal("0.00")

    @property
    def saldo_calculado(self) -> Decimal:
        """Alias para saldo_movimentos."""
        return self.saldo_movimentos


class MovimentoCaixa(TenantAwareModel):
    """
    Movimentação individual de caixa.
    """

    abertura = models.ForeignKey(
        AberturaCaixa,
        on_delete=models.PROTECT,
        related_name="movimentos",
        verbose_name=_("abertura"),
    )
    tipo = models.CharField(
        _("tipo"),
        max_length=20,
        choices=TipoMovimento.choices,
    )
    forma_pagamento = models.ForeignKey(
        "core.FormaPagamento",
        on_delete=models.PROTECT,
        related_name="movimentos",
        verbose_name=_("forma de pagamento"),
    )
    valor = models.DecimalField(
        _("valor"),
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    descricao = models.TextField(
        _("descrição"),
        blank=True,
    )

    # Vinculação com NFS-e (opcional)
    nota_fiscal = models.ForeignKey(
        "nfse.NotaFiscalServico",
        on_delete=models.SET_NULL,
        related_name="movimentos_caixa",
        verbose_name=_("nota fiscal"),
        null=True,
        blank=True,
    )

    # Cliente (para movimentos sem NFS-e)
    cliente = models.ForeignKey(
        "clientes.Cliente",
        on_delete=models.SET_NULL,
        related_name="movimentos_caixa",
        verbose_name=_("cliente"),
        null=True,
        blank=True,
    )

    # Referência a movimento estornado (para tipo ESTORNO)
    movimento_estornado = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        related_name="estorno",
        verbose_name=_("movimento estornado"),
        null=True,
        blank=True,
    )

    # Auditoria
    hash_registro = models.CharField(
        _("hash do registro"),
        max_length=64,
        editable=False,
    )
    hash_anterior = models.CharField(
        _("hash anterior"),
        max_length=64,
        blank=True,
        editable=False,
    )

    # Data/hora do movimento
    data_hora = models.DateTimeField(
        _("data/hora"),
        default=timezone.now,
    )

    class Meta:
        verbose_name = _("movimento de caixa")
        verbose_name_plural = _("movimentos de caixa")
        ordering = ["-data_hora"]

    def __str__(self):
        return f"{self.get_tipo_display()} - R$ {self.valor}"

    def save(self, *args, **kwargs):
        """Generate hash before saving."""
        if not self.hash_registro:
            # Get previous hash
            last_movimento = (
                MovimentoCaixa.objects.filter(abertura=self.abertura)
                .order_by("-created_at")
                .first()
            )

            self.hash_anterior = (
                last_movimento.hash_registro if last_movimento else self.abertura.hash_registro
            )

            # Generate hash
            data = {
                "abertura_id": str(self.abertura_id),
                "tipo": self.tipo,
                "forma_pagamento_id": str(self.forma_pagamento_id),
                "valor": str(self.valor),
                "data_hora": str(self.data_hora),
            }
            self.hash_registro = generate_hash(data, self.hash_anterior)

        super().save(*args, **kwargs)

    @property
    def is_entrada(self) -> bool:
        """Verifica se é movimento de entrada."""
        return self.tipo in [TipoMovimento.ENTRADA, TipoMovimento.SUPRIMENTO]

    @property
    def is_saida(self) -> bool:
        """Verifica se é movimento de saída."""
        return self.tipo in [TipoMovimento.SAIDA, TipoMovimento.SANGRIA, TipoMovimento.ESTORNO]


class FechamentoCaixa(TenantAwareModel):
    """
    Registro de fechamento de caixa com conferência.
    """

    abertura = models.OneToOneField(
        AberturaCaixa,
        on_delete=models.PROTECT,
        related_name="fechamento",
        verbose_name=_("abertura"),
    )
    operador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="fechamentos_caixa",
        verbose_name=_("operador"),
    )
    data_hora = models.DateTimeField(
        _("data/hora fechamento"),
        default=timezone.now,
    )

    # Valores
    saldo_sistema = models.DecimalField(
        _("saldo sistema"),
        max_digits=14,
        decimal_places=2,
        help_text=_("Saldo calculado pelo sistema"),
    )
    saldo_informado = models.DecimalField(
        _("saldo informado"),
        max_digits=14,
        decimal_places=2,
        help_text=_("Saldo informado pelo operador"),
    )
    diferenca = models.DecimalField(
        _("diferença"),
        max_digits=14,
        decimal_places=2,
        help_text=_("Diferença entre sistema e informado"),
    )

    # Detalhamento por forma de pagamento
    detalhamento = models.JSONField(
        _("detalhamento"),
        default=dict,
        help_text=_("Totais por forma de pagamento"),
    )

    # Justificativa (obrigatória se houver diferença)
    justificativa_diferenca = models.TextField(
        _("justificativa da diferença"),
        blank=True,
    )

    # Aprovação em dupla
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=StatusFechamento.choices,
        default=StatusFechamento.PENDENTE,
    )
    aprovador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="fechamentos_aprovados",
        verbose_name=_("aprovador"),
        null=True,
        blank=True,
    )
    data_aprovacao = models.DateTimeField(
        _("data aprovação"),
        null=True,
        blank=True,
    )
    observacao_aprovador = models.TextField(
        _("observação do aprovador"),
        blank=True,
    )

    # Auditoria
    hash_registro = models.CharField(
        _("hash do registro"),
        max_length=64,
        editable=False,
    )

    class Meta:
        verbose_name = _("fechamento de caixa")
        verbose_name_plural = _("fechamentos de caixa")
        ordering = ["-data_hora"]

    def __str__(self):
        return f"Fechamento {self.abertura.caixa.identificador} - {self.data_hora.strftime('%d/%m/%Y %H:%M')}"

    def save(self, *args, **kwargs):
        """Calculate difference and generate hash."""
        self.diferenca = self.saldo_informado - self.saldo_sistema

        if not self.hash_registro:
            data = {
                "abertura_id": str(self.abertura_id),
                "operador_id": str(self.operador_id),
                "saldo_sistema": str(self.saldo_sistema),
                "saldo_informado": str(self.saldo_informado),
                "data_hora": str(self.data_hora),
            }
            self.hash_registro = generate_hash(data, self.abertura.hash_registro)

        super().save(*args, **kwargs)

    @property
    def tem_diferenca(self) -> bool:
        """Verifica se há diferença no fechamento."""
        return self.diferenca != Decimal("0.00")

    @property
    def requer_aprovacao(self) -> bool:
        """Verifica se fechamento requer aprovação."""
        # Requer aprovação se houver diferença maior que tolerância
        tolerancia = Decimal("1.00")  # Configurável
        return abs(self.diferenca) > tolerancia

    def aprovar(self, aprovador, observacao: str = ""):
        """Aprova o fechamento."""
        self.status = StatusFechamento.APROVADO
        self.aprovador = aprovador
        self.data_aprovacao = timezone.now()
        self.observacao_aprovador = observacao
        self.save()

        # Marca abertura como fechada
        self.abertura.fechado = True
        self.abertura.save(update_fields=["fechado"])

        # Atualiza status do caixa
        self.abertura.caixa.status = StatusCaixa.FECHADO
        self.abertura.caixa.operador_atual = None
        self.abertura.caixa.save(update_fields=["status", "operador_atual"])

    def rejeitar(self, aprovador, observacao: str):
        """Rejeita o fechamento."""
        self.status = StatusFechamento.REJEITADO
        self.aprovador = aprovador
        self.data_aprovacao = timezone.now()
        self.observacao_aprovador = observacao
        self.save()
