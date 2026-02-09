"""
Clientes models - Tomadores de Serviço.
"""

import hashlib
import re

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from caixa_nfse.core.models import TenantAwareModel


def validar_cpf(cpf: str) -> bool:
    """Valida CPF brasileiro."""
    cpf = re.sub(r"[^0-9]", "", cpf)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False

    for i in range(9, 11):
        valor = sum(int(cpf[num]) * ((i + 1) - num) for num in range(0, i))
        digito = ((valor * 10) % 11) % 10
        if digito != int(cpf[i]):
            return False
    return True


def validar_cnpj(cnpj: str) -> bool:
    """Valida CNPJ brasileiro."""
    cnpj = re.sub(r"[^0-9]", "", cnpj)
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False

    for i, multiplicadores in [
        (12, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]),
        (13, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]),
    ]:
        soma = sum(int(cnpj[j]) * multiplicadores[j] for j in range(i))
        resto = soma % 11
        digito = 0 if resto < 2 else 11 - resto
        if digito != int(cnpj[i]):
            return False
    return True


class TipoPessoa(models.TextChoices):
    """Tipo de pessoa."""

    PF = "PF", _("Pessoa Física")
    PJ = "PJ", _("Pessoa Jurídica")
    ESTRANGEIRO = "EX", _("Estrangeiro")


class Cliente(TenantAwareModel):
    """
    Tomador de serviço para NFS-e.
    Dados pessoais são criptografados conforme LGPD.
    """

    # Tipo
    tipo_pessoa = models.CharField(
        _("tipo de pessoa"),
        max_length=2,
        choices=TipoPessoa.choices,
        default=TipoPessoa.PF,
    )

    # Documento (armazenado com hash para busca)
    cpf_cnpj = models.CharField(
        _("CPF/CNPJ"),
        max_length=18,
        blank=True,
        default="",
        help_text=_("Documento com máscara"),
    )
    cpf_cnpj_hash = models.CharField(
        _("hash do documento"),
        max_length=64,
        blank=True,
        default="",
        db_index=True,
        editable=False,
    )

    # Identificação
    razao_social = models.CharField(
        _("razão social / nome"),
        max_length=255,
    )
    nome_fantasia = models.CharField(
        _("nome fantasia"),
        max_length=255,
        blank=True,
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

    # Contato
    email = models.EmailField(_("e-mail"), blank=True)
    telefone = models.CharField(_("telefone"), max_length=20, blank=True)

    # Endereço
    logradouro = models.CharField(_("logradouro"), max_length=255, blank=True)
    numero = models.CharField(_("número"), max_length=20, blank=True)
    complemento = models.CharField(_("complemento"), max_length=100, blank=True)
    bairro = models.CharField(_("bairro"), max_length=100, blank=True)
    cidade = models.CharField(_("cidade"), max_length=100, blank=True)
    uf = models.CharField(_("UF"), max_length=2, blank=True)
    cep = models.CharField(_("CEP"), max_length=9, blank=True)
    codigo_ibge = models.CharField(_("código IBGE"), max_length=7, blank=True)

    # LGPD
    consentimento_lgpd = models.BooleanField(
        _("consentimento LGPD"),
        default=False,
        help_text=_("Cliente autorizou o uso dos dados"),
    )
    data_consentimento = models.DateTimeField(
        _("data do consentimento"),
        null=True,
        blank=True,
    )

    # Status
    ativo = models.BooleanField(_("ativo"), default=True)
    cadastro_completo = models.BooleanField(
        _("cadastro completo"),
        default=True,
        help_text=_("Indica se o cliente tem todos os dados preenchidos (CPF, endereço, etc.)"),
    )

    class Meta:
        verbose_name = _("cliente")
        verbose_name_plural = _("clientes")
        ordering = ["razao_social"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "cpf_cnpj_hash"],
                name="unique_cliente_documento",
                condition=models.Q(cpf_cnpj_hash__gt=""),
            ),
        ]

    def __str__(self):
        return f"{self.razao_social} ({self.cpf_cnpj})"

    def get_absolute_url(self):
        from django.urls import reverse

        return reverse("clientes:detail", kwargs={"pk": self.pk})

    def clean(self):
        """Validate CPF/CNPJ based on tipo_pessoa."""
        super().clean()

        if not self.cpf_cnpj:
            return

        if self.tipo_pessoa == TipoPessoa.PF:
            if not validar_cpf(self.cpf_cnpj):
                raise ValidationError({"cpf_cnpj": _("CPF inválido.")})
        elif self.tipo_pessoa == TipoPessoa.PJ:
            if not validar_cnpj(self.cpf_cnpj):
                raise ValidationError({"cpf_cnpj": _("CNPJ inválido.")})

    def save(self, *args, **kwargs):
        # Generate hash for indexed search (only if document provided)
        if self.cpf_cnpj:
            doc_limpo = re.sub(r"[^0-9]", "", self.cpf_cnpj)
            self.cpf_cnpj_hash = hashlib.sha256(doc_limpo.encode()).hexdigest()
        else:
            self.cpf_cnpj_hash = ""
        super().save(*args, **kwargs)

    @property
    def endereco_completo(self) -> str:
        """Retorna endereço formatado."""
        partes = [
            self.logradouro,
            self.numero,
            self.complemento,
            self.bairro,
            f"{self.cidade}/{self.uf}" if self.cidade else "",
            self.cep,
        ]
        return ", ".join(p for p in partes if p)

    @property
    def documento_formatado(self) -> str:
        """Retorna documento com máscara."""
        doc = re.sub(r"[^0-9]", "", self.cpf_cnpj)
        if len(doc) == 11:
            return f"{doc[:3]}.{doc[3:6]}.{doc[6:9]}-{doc[9:]}"
        elif len(doc) == 14:
            return f"{doc[:2]}.{doc[2:5]}.{doc[5:8]}/{doc[8:12]}-{doc[12:]}"
        return self.cpf_cnpj
