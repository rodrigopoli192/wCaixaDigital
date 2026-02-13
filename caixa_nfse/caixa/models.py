"""
Caixa models - Cash register operations.
"""

from datetime import date
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


class StatusRecebimento(models.TextChoices):
    """Status de recebimento parcial de protocolo."""

    PENDENTE = "PENDENTE", _("Pendente")
    PARCIAL = "PARCIAL", _("Parcial")
    QUITADO = "QUITADO", _("Quitado")
    VENCIDO = "VENCIDO", _("Vencido")


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

    # Edição de saldo inicial (once-per-day)
    saldo_inicial_editado = models.BooleanField(
        _("saldo inicial editado"),
        default=False,
        help_text=_("Se True, já foi editado hoje e não pode ser alterado novamente"),
    )
    saldo_inicial_original = models.DecimalField(
        _("saldo inicial original"),
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Valor original antes da edição (para auditoria)"),
    )
    saldo_editado_em = models.DateTimeField(
        _("editado em"),
        null=True,
        blank=True,
        help_text=_("Data/hora da última edição"),
    )
    saldo_editado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="aberturas_editadas",
        verbose_name=_("editado por"),
        null=True,
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
    def pode_editar_saldo_inicial(self) -> bool:
        """
        Retorna True se o saldo inicial ainda pode ser editado hoje.
        Regras:
        - Caixa não pode estar fechado
        - Deve ser no mesmo dia da abertura
        - Não pode ter sido editado antes (once-per-day)
        """
        if self.fechado:
            return False
        if self.data_hora.date() != timezone.now().date():
            return False
        if self.saldo_inicial_editado:
            return False
        return True

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

    @property
    def is_operacional_hoje(self) -> bool:
        """Verifica se a abertura é do dia atual."""
        return self.data_hora.date() == timezone.localdate()


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

    # --- Dados do Ato / Certidão ---
    protocolo = models.CharField(
        _("protocolo"),
        max_length=50,
        blank=True,
        default="",
    )
    status_item = models.CharField(
        _("status do item"),
        max_length=30,
        blank=True,
        default="",
    )
    quantidade = models.PositiveIntegerField(
        _("quantidade"),
        default=1,
        blank=True,
        null=True,
    )
    cliente_nome = models.CharField(
        _("nome do apresentante"),
        max_length=200,
        blank=True,
        default="",
    )

    # --- Taxas Cartoriais ---
    iss = models.DecimalField(
        _("ISS"),
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        blank=True,
    )
    fundesp = models.DecimalField(
        _("FUNDESP"),
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        blank=True,
    )
    funesp = models.DecimalField(
        _("FUNESP"),
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        blank=True,
    )
    estado = models.DecimalField(
        _("ESTADO"),
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        blank=True,
    )
    fesemps = models.DecimalField(
        _("FESEMPS"),
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        blank=True,
    )
    funemp = models.DecimalField(
        _("FUNEMP"),
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        blank=True,
    )
    funcomp = models.DecimalField(
        _("FUNCOMP"),
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        blank=True,
    )
    fepadsaj = models.DecimalField(
        _("FEPADSAJ"),
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        blank=True,
    )
    funproge = models.DecimalField(
        _("FUNPROGE"),
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        blank=True,
    )
    fundepeg = models.DecimalField(
        _("FUNDEPEG"),
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        blank=True,
    )
    fundaf = models.DecimalField(
        _("FUNDAF"),
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        blank=True,
    )
    femal = models.DecimalField(
        _("FEMAL"),
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        blank=True,
    )
    fecad = models.DecimalField(
        _("FECAD"),
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        blank=True,
    )
    emolumento = models.DecimalField(
        _("emolumento"),
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        blank=True,
    )
    taxa_judiciaria = models.DecimalField(
        _("taxa judiciária"),
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        blank=True,
    )
    valor_receita_adicional_1 = models.DecimalField(
        _("Receita Adicional 1"),
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        blank=True,
    )
    valor_receita_adicional_2 = models.DecimalField(
        _("Receita Adicional 2"),
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
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

    data_ato = models.DateField(
        _("data do ato"),
        null=True,
        blank=True,
        help_text=_("Data da confecção do ato (importada da SQL)"),
    )

    # Campos de taxa para iteração
    TAXA_FIELDS = [
        "iss",
        "fundesp",
        "funesp",
        "estado",
        "fesemps",
        "funemp",
        "funcomp",
        "fepadsaj",
        "funproge",
        "fundepeg",
        "fundaf",
        "femal",
        "fecad",
        "emolumento",
        "taxa_judiciaria",
        "valor_receita_adicional_1",
        "valor_receita_adicional_2",
    ]

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
    def valor_total_taxas(self) -> Decimal:
        """Soma de todas as taxas cartoriais."""
        return sum(getattr(self, f) or Decimal("0.00") for f in self.TAXA_FIELDS)

    FUNDOS_FIELDS = [f for f in TAXA_FIELDS if f not in ("emolumento",)]

    @property
    def valor_total_fundos(self) -> Decimal:
        """Soma de taxas e fundos (sem emolumento)."""
        return sum(getattr(self, f) or Decimal("0.00") for f in self.FUNDOS_FIELDS)

    @property
    def is_entrada(self) -> bool:
        """Verifica se é movimento de entrada."""
        return self.tipo in [TipoMovimento.ENTRADA, TipoMovimento.SUPRIMENTO]

    @property
    def is_saida(self) -> bool:
        """Verifica se é movimento de saída."""
        return self.tipo in [TipoMovimento.SAIDA, TipoMovimento.SANGRIA, TipoMovimento.ESTORNO]

    @property
    def importado_origem(self):
        """Retorna o MovimentoImportado vinculado via ParcelaRecebimento."""
        parcela = self.parcela_recebimento.select_related("movimento_importado").first()
        return parcela.movimento_importado if parcela else None


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

    justificativa_diferenca = models.TextField(
        _("justificativa da diferença"),
        blank=True,
    )

    observacao = models.TextField(
        _("observação"),
        blank=True,
        help_text=_("Observações gerais do operador"),
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


class MovimentoImportado(TenantAwareModel):
    """
    Staging table for movements imported from external databases via Rotinas SQL.
    Data is stored temporarily here until confirmed and migrated to MovimentoCaixa.
    """

    abertura = models.ForeignKey(
        AberturaCaixa,
        verbose_name=_("abertura"),
        on_delete=models.CASCADE,
        related_name="importados",
    )
    conexao = models.ForeignKey(
        "core.ConexaoExterna",
        verbose_name=_("conexão"),
        on_delete=models.SET_NULL,
        null=True,
        related_name="importados",
    )
    rotina = models.ForeignKey(
        "backoffice.Rotina",
        verbose_name=_("rotina"),
        on_delete=models.SET_NULL,
        null=True,
        related_name="importados",
    )
    importado_em = models.DateTimeField(_("importado em"), auto_now_add=True)
    importado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("importado por"),
        on_delete=models.SET_NULL,
        null=True,
        related_name="importacoes",
    )

    # Confirmation status
    confirmado = models.BooleanField(_("confirmado"), default=False)
    confirmado_em = models.DateTimeField(_("confirmado em"), null=True, blank=True)
    movimento_destino = models.ForeignKey(
        MovimentoCaixa,
        verbose_name=_("movimento destino"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="importacao_origem",
    )

    # Mirrored data fields
    protocolo = models.CharField(_("protocolo"), max_length=100, blank=True, default="")
    status_item = models.CharField(_("status do item"), max_length=100, blank=True, default="")
    quantidade = models.PositiveIntegerField(_("quantidade"), default=1, blank=True, null=True)
    valor = models.DecimalField(
        _("valor"),
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        blank=True,
    )
    descricao = models.CharField(_("descrição"), max_length=500, blank=True, default="")
    cliente_nome = models.CharField(
        _("nome do apresentante"),
        max_length=200,
        blank=True,
        default="",
    )

    # Tax fields
    iss = models.DecimalField(
        _("ISS"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    fundesp = models.DecimalField(
        _("FUNDESP"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    funesp = models.DecimalField(
        _("FUNESP"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    estado = models.DecimalField(
        _("Estado"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    fesemps = models.DecimalField(
        _("FESEMPS"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    funemp = models.DecimalField(
        _("FUNEMP"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    funcomp = models.DecimalField(
        _("FUNCOMP"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    fepadsaj = models.DecimalField(
        _("FEPADSAJ"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    funproge = models.DecimalField(
        _("FUNPROGE"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    fundepeg = models.DecimalField(
        _("FUNDEPEG"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    fundaf = models.DecimalField(
        _("FUNDAF"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    femal = models.DecimalField(
        _("FEMAL"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    fecad = models.DecimalField(
        _("FECAD"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    emolumento = models.DecimalField(
        _("emolumento"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    taxa_judiciaria = models.DecimalField(
        _("taxa judiciária"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    valor_receita_adicional_1 = models.DecimalField(
        _("Receita Adicional 1"),
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        blank=True,
    )
    valor_receita_adicional_2 = models.DecimalField(
        _("Receita Adicional 2"),
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        blank=True,
    )

    data_ato = models.DateField(
        _("data do ato"),
        null=True,
        blank=True,
        help_text=_("Data da confecção do ato (importada da SQL)"),
    )

    # --- Recebimento Parcial ---
    status_recebimento = models.CharField(
        _("status de recebimento"),
        max_length=20,
        choices=StatusRecebimento.choices,
        default=StatusRecebimento.PENDENTE,
    )
    prazo_quitacao = models.DateField(
        _("prazo de quitação"),
        null=True,
        blank=True,
        help_text=_("Data limite para quitação total do protocolo"),
    )

    TAXA_FIELDS = MovimentoCaixa.TAXA_FIELDS

    class Meta:
        verbose_name = _("movimento importado")
        verbose_name_plural = _("movimentos importados")
        ordering = ["-importado_em"]

    def __str__(self):
        return f"Import #{self.pk} - {self.protocolo or 'S/P'}"

    FUNDOS_FIELDS = MovimentoCaixa.FUNDOS_FIELDS

    @property
    def valor_total_taxas(self) -> Decimal:
        return sum(getattr(self, f) or Decimal("0.00") for f in self.TAXA_FIELDS)

    @property
    def valor_total_fundos(self) -> Decimal:
        """Soma de taxas e fundos (sem emolumento)."""
        return sum(getattr(self, f) or Decimal("0.00") for f in self.FUNDOS_FIELDS)

    @property
    def valor_recebido(self) -> Decimal:
        """Soma de todas as parcelas recebidas."""
        from django.db.models import Sum

        return self.parcelas.aggregate(total=Sum("valor"))["total"] or Decimal("0.00")

    @property
    def saldo_pendente(self) -> Decimal:
        """Valor restante a receber."""
        return (self.valor or Decimal("0.00")) - self.valor_recebido

    @property
    def percentual_recebido(self) -> int:
        """Percentual recebido (0-100)."""
        if not self.valor:
            return 0
        return int((self.valor_recebido / self.valor) * 100)

    @property
    def prazo_vencido(self) -> bool:
        """True se prazo de quitação passou e não está quitado."""
        if not self.prazo_quitacao:
            return False
        return (
            date.today() > self.prazo_quitacao
            and self.status_recebimento != StatusRecebimento.QUITADO
        )


class ParcelaRecebimento(TenantAwareModel):
    """Registro de cada parcela recebida de um protocolo."""

    movimento_importado = models.ForeignKey(
        MovimentoImportado,
        on_delete=models.CASCADE,
        related_name="parcelas",
        verbose_name=_("movimento importado"),
    )
    movimento_caixa = models.ForeignKey(
        MovimentoCaixa,
        on_delete=models.PROTECT,
        related_name="parcela_recebimento",
        verbose_name=_("movimento de caixa"),
    )
    abertura = models.ForeignKey(
        AberturaCaixa,
        on_delete=models.PROTECT,
        related_name="parcelas_recebidas",
        verbose_name=_("abertura"),
    )
    forma_pagamento = models.ForeignKey(
        "core.FormaPagamento",
        on_delete=models.PROTECT,
        related_name="parcelas_recebimento",
        verbose_name=_("forma de pagamento"),
    )
    valor = models.DecimalField(
        _("valor da parcela"),
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    numero_parcela = models.PositiveIntegerField(
        _("número da parcela"),
        default=1,
    )
    recebido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="parcelas_recebidas",
        verbose_name=_("recebido por"),
    )
    recebido_em = models.DateTimeField(
        _("recebido em"),
        default=timezone.now,
    )
    observacao = models.TextField(
        _("observação"),
        blank=True,
    )

    class Meta:
        verbose_name = _("parcela de recebimento")
        verbose_name_plural = _("parcelas de recebimento")
        ordering = ["numero_parcela"]

    def __str__(self):
        return f"Parcela {self.numero_parcela} - R$ {self.valor}"


class ItemAtoImportado(TenantAwareModel):
    """
    Detalhe individual de cada ato dentro de um MovimentoImportado agrupado.
    Preserva os dados granulares de cada linha SQL antes do agrupamento.
    """

    movimento_importado = models.ForeignKey(
        MovimentoImportado,
        on_delete=models.CASCADE,
        related_name="itens",
        verbose_name=_("movimento importado"),
    )
    descricao = models.CharField(_("descrição"), max_length=500, blank=True, default="")
    valor = models.DecimalField(
        _("valor"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    quantidade = models.PositiveIntegerField(_("quantidade"), default=1, blank=True, null=True)
    data_ato = models.DateField(_("data do ato"), null=True, blank=True)
    status_item = models.CharField(_("status do item"), max_length=100, blank=True, default="")
    cliente_nome = models.CharField(
        _("nome do apresentante"), max_length=200, blank=True, default=""
    )

    # Tax fields (same as parent)
    iss = models.DecimalField(
        _("ISS"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    fundesp = models.DecimalField(
        _("FUNDESP"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    funesp = models.DecimalField(
        _("FUNESP"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    estado = models.DecimalField(
        _("Estado"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    fesemps = models.DecimalField(
        _("FESEMPS"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    funemp = models.DecimalField(
        _("FUNEMP"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    funcomp = models.DecimalField(
        _("FUNCOMP"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    fepadsaj = models.DecimalField(
        _("FEPADSAJ"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    funproge = models.DecimalField(
        _("FUNPROGE"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    fundepeg = models.DecimalField(
        _("FUNDEPEG"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    fundaf = models.DecimalField(
        _("FUNDAF"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    femal = models.DecimalField(
        _("FEMAL"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    fecad = models.DecimalField(
        _("FECAD"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    emolumento = models.DecimalField(
        _("emolumento"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    taxa_judiciaria = models.DecimalField(
        _("taxa judiciária"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    valor_receita_adicional_1 = models.DecimalField(
        _("Receita Adicional 1"),
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        blank=True,
    )
    valor_receita_adicional_2 = models.DecimalField(
        _("Receita Adicional 2"),
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        blank=True,
    )

    TAXA_FIELDS = MovimentoCaixa.TAXA_FIELDS

    class Meta:
        verbose_name = _("item de ato importado")
        verbose_name_plural = _("itens de atos importados")
        ordering = ["created_at"]

    def __str__(self):
        return f"Item #{self.pk} - {self.descricao[:50] or 'S/D'}"

    @property
    def valor_total_taxas(self) -> Decimal:
        return sum(getattr(self, f) or Decimal("0.00") for f in self.TAXA_FIELDS)


class ItemAtoMovimento(TenantAwareModel):
    """
    Detalhe individual de cada ato dentro de um MovimentoCaixa confirmado.
    Persistência permanente para recibos detalhados.
    """

    movimento = models.ForeignKey(
        MovimentoCaixa,
        on_delete=models.CASCADE,
        related_name="itens",
        verbose_name=_("movimento"),
    )
    descricao = models.CharField(_("descrição"), max_length=500, blank=True, default="")
    valor = models.DecimalField(
        _("valor"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    quantidade = models.PositiveIntegerField(_("quantidade"), default=1, blank=True, null=True)
    data_ato = models.DateField(_("data do ato"), null=True, blank=True)
    status_item = models.CharField(_("status do item"), max_length=100, blank=True, default="")
    cliente_nome = models.CharField(
        _("nome do apresentante"), max_length=200, blank=True, default=""
    )

    # Tax fields (same as parent)
    iss = models.DecimalField(
        _("ISS"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    fundesp = models.DecimalField(
        _("FUNDESP"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    funesp = models.DecimalField(
        _("FUNESP"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    estado = models.DecimalField(
        _("Estado"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    fesemps = models.DecimalField(
        _("FESEMPS"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    funemp = models.DecimalField(
        _("FUNEMP"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    funcomp = models.DecimalField(
        _("FUNCOMP"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    fepadsaj = models.DecimalField(
        _("FEPADSAJ"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    funproge = models.DecimalField(
        _("FUNPROGE"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    fundepeg = models.DecimalField(
        _("FUNDEPEG"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    fundaf = models.DecimalField(
        _("FUNDAF"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    femal = models.DecimalField(
        _("FEMAL"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    fecad = models.DecimalField(
        _("FECAD"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    emolumento = models.DecimalField(
        _("emolumento"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    taxa_judiciaria = models.DecimalField(
        _("taxa judiciária"), max_digits=14, decimal_places=2, default=Decimal("0.00"), blank=True
    )
    valor_receita_adicional_1 = models.DecimalField(
        _("Receita Adicional 1"),
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        blank=True,
    )
    valor_receita_adicional_2 = models.DecimalField(
        _("Receita Adicional 2"),
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        blank=True,
    )

    TAXA_FIELDS = MovimentoCaixa.TAXA_FIELDS

    class Meta:
        verbose_name = _("item de ato do movimento")
        verbose_name_plural = _("itens de atos do movimento")
        ordering = ["created_at"]

    def __str__(self):
        return f"Item #{self.pk} - {self.descricao[:50] or 'S/D'}"

    @property
    def valor_total_taxas(self) -> Decimal:
        return sum(getattr(self, f) or Decimal("0.00") for f in self.TAXA_FIELDS)
