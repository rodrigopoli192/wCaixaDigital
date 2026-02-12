"""
Service para geração de NFS-e a partir de movimentos de caixa.

Converte movimentos confirmados em notas fiscais prontas para emissão,
preenchendo todos os campos obrigatórios do NotaFiscalServico.
"""

import logging
from decimal import Decimal

from django.utils import timezone

logger = logging.getLogger(__name__)


def criar_nfse_de_movimento(movimento, servico_municipal=None):
    """
    Cria uma NotaFiscalServico a partir de um MovimentoCaixa.

    Args:
        movimento: Instância de MovimentoCaixa confirmada.
        servico_municipal: ServicoMunicipal a usar. Se None, busca o primeiro
            ativo do tenant.

    Returns:
        NotaFiscalServico criada com status RASCUNHO.

    Raises:
        ValueError: Se dados obrigatórios estiverem ausentes.
    """
    from caixa_nfse.nfse.models import (
        ConfiguracaoNFSe,
        NotaFiscalServico,
        ServicoMunicipal,
        StatusNFSe,
    )

    tenant = movimento.tenant

    # Validação: cliente obrigatório
    cliente = movimento.cliente
    if not cliente:
        raise ValueError(f"Movimento {movimento.pk} sem cliente vinculado — impossível gerar NFS-e")

    # Buscar serviço municipal
    if servico_municipal is None:
        servico_municipal = ServicoMunicipal.objects.first()
        if servico_municipal is None:
            raise ValueError("Nenhum serviço municipal cadastrado no sistema")

    # Buscar configuração NFS-e do tenant
    config = ConfiguracaoNFSe.objects.filter(tenant=tenant).first()
    ambiente = config.ambiente if config else "HOMOLOGACAO"
    backend = config.backend if config else "mock"

    # Gerar número RPS
    numero_rps = tenant.proximo_numero_rps()
    serie_rps = getattr(tenant, "nfse_serie_padrao", "1") or "1"

    # Montar discriminação
    discriminacao = movimento.descricao or f"Serviço ref. protocolo {movimento.protocolo}"

    # Alíquota ISS padrão do serviço ou fallback
    aliquota_iss = getattr(servico_municipal, "aliquota_padrao", None) or Decimal("0.0500")

    # Valor líquido e base de cálculo
    valor_servicos = movimento.valor
    valor_deducoes = Decimal("0.00")
    base_calculo = valor_servicos - valor_deducoes
    valor_iss = base_calculo * aliquota_iss
    valor_liquido = valor_servicos - valor_iss

    # Local de prestação IBGE — usar município do serviço ou padrão
    local_ibge = getattr(servico_municipal, "municipio_ibge", "3550308")

    nota = NotaFiscalServico.objects.create(
        tenant=tenant,
        cliente=cliente,
        numero_rps=numero_rps,
        serie_rps=serie_rps,
        servico=servico_municipal,
        discriminacao=discriminacao,
        competencia=timezone.now().date().replace(day=1),
        data_emissao=timezone.now().date(),
        valor_servicos=valor_servicos,
        valor_deducoes=valor_deducoes,
        base_calculo=base_calculo,
        aliquota_iss=aliquota_iss,
        valor_iss=valor_iss,
        valor_liquido=valor_liquido,
        local_prestacao_ibge=local_ibge,
        status=StatusNFSe.RASCUNHO,
        ambiente=ambiente,
        backend_utilizado=backend,
    )

    # Vincular movimento → nota
    movimento.nota_fiscal = nota
    movimento.save(update_fields=["nota_fiscal"])

    logger.info(
        "NFS-e %s criada a partir do movimento %s (RPS %d)",
        nota.pk,
        movimento.pk,
        numero_rps,
    )

    return nota
