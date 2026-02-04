"""
Fiscal models - Tax reports and books.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from caixa_nfse.core.models import TenantAwareModel


class LivroFiscalServicos(TenantAwareModel):
    """Livro de Registro de Serviços Prestados por período."""

    competencia = models.DateField(_("competência"), db_index=True)
    municipio_ibge = models.CharField(_("município IBGE"), max_length=7)

    # Totalizadores
    total_notas = models.PositiveIntegerField(_("total notas"), default=0)
    valor_servicos = models.DecimalField(_("valor serviços"), max_digits=14, decimal_places=2)
    valor_iss = models.DecimalField(_("valor ISS"), max_digits=14, decimal_places=2)
    valor_iss_retido = models.DecimalField(_("ISS retido"), max_digits=14, decimal_places=2)

    # Status
    fechado = models.BooleanField(_("fechado"), default=False)
    data_fechamento = models.DateTimeField(_("data fechamento"), null=True, blank=True)

    class Meta:
        verbose_name = _("livro fiscal de serviços")
        verbose_name_plural = _("livros fiscais de serviços")
        ordering = ["-competencia"]
        unique_together = [["tenant", "competencia", "municipio_ibge"]]

    def __str__(self):
        return f"Livro {self.competencia.strftime('%m/%Y')} - {self.municipio_ibge}"
