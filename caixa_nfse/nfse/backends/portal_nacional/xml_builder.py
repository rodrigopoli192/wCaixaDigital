"""
Construtor de XML DPS (Declaração Prévia de Serviços) no padrão nacional.

Gera o XML da DPS conforme especificação do Portal Nacional NFS-e,
incluindo dados do prestador, tomador, serviço, valores, tributos (ISS, CBS, IBS)
e informações complementares.
"""

from decimal import Decimal

from lxml import etree

NSMAP = {
    None: "http://www.sped.fazenda.gov.br/nfse",
}

NS = "{http://www.sped.fazenda.gov.br/nfse}"


def construir_dps(nota, tenant) -> etree._Element:
    """
    Constrói o XML da DPS a partir de uma NotaFiscalServico e do Tenant.

    Retorna o elemento raiz <DPS> pronto para assinatura.
    """
    dps = etree.Element(f"{NS}DPS", nsmap=NSMAP)
    inf_dps = etree.SubElement(dps, f"{NS}infDPS", Id=_gerar_id_dps(nota, tenant))

    _adicionar_identificacao(inf_dps, nota, tenant)
    _adicionar_prestador(inf_dps, tenant)
    _adicionar_tomador(inf_dps, nota)
    _adicionar_servico(inf_dps, nota)
    _adicionar_valores(inf_dps, nota)
    _adicionar_ibs_cbs(inf_dps, nota)

    return dps


def dps_para_string(dps: etree._Element) -> str:
    """Serializa o elemento DPS para string XML."""
    return etree.tostring(
        dps,
        xml_declaration=True,
        encoding="UTF-8",
        pretty_print=False,
    ).decode("UTF-8")


def _gerar_id_dps(nota, tenant) -> str:
    """Gera o ID da DPS no formato: DPS + CNPJ(14) + série(5) + número(15)."""
    cnpj = (tenant.cnpj or "").replace(".", "").replace("/", "").replace("-", "")
    serie = str(nota.serie_rps).zfill(5)
    numero = str(nota.numero_rps).zfill(15)
    return f"DPS{cnpj}{serie}{numero}"


def _adicionar_identificacao(parent: etree._Element, nota, tenant) -> None:
    """Adiciona o grupo <Identificação> com dados gerais da DPS."""
    ident = etree.SubElement(parent, f"{NS}Id")

    _sub_text(ident, "cLocEmi", str(nota.local_prestacao_ibge))
    _sub_text(ident, "dhEmi", nota.data_emissao.isoformat())
    _sub_text(ident, "serie", str(nota.serie_rps).zfill(5))
    _sub_text(ident, "nDPS", str(nota.numero_rps).zfill(15))
    _sub_text(ident, "tpAmb", "1" if nota.ambiente == "PRODUCAO" else "2")
    # Tipo de emissão: 1 = Normal
    _sub_text(ident, "tpEmit", "1")


def _adicionar_prestador(parent: etree._Element, tenant) -> None:
    """Adiciona dados do prestador de serviço (tenant)."""
    prest = etree.SubElement(parent, f"{NS}prest")

    cnpj = (tenant.cnpj or "").replace(".", "").replace("/", "").replace("-", "")
    _sub_text(prest, "CNPJ", cnpj)
    _sub_text(prest, "IM", tenant.inscricao_municipal or "")
    _sub_text(prest, "xNome", tenant.razao_social or "")

    # Endereço
    end = etree.SubElement(prest, f"{NS}end")
    _sub_text(end, "xLgr", tenant.logradouro or "")
    _sub_text(end, "nro", tenant.numero or "S/N")
    _sub_text(end, "xBairro", tenant.bairro or "")
    _sub_text(end, "cMun", "3550308")  # TODO: campo no Tenant
    _sub_text(end, "UF", tenant.uf or "")
    _sub_text(end, "CEP", (tenant.cep or "").replace("-", ""))


def _adicionar_tomador(parent: etree._Element, nota) -> None:
    """Adiciona dados do tomador do serviço (cliente)."""
    toma = etree.SubElement(parent, f"{NS}toma")

    cliente = nota.cliente
    doc = (cliente.cpf_cnpj or "").replace(".", "").replace("-", "").replace("/", "")

    if len(doc) == 14:
        _sub_text(toma, "CNPJ", doc)
    elif len(doc) == 11:
        _sub_text(toma, "CPF", doc)

    _sub_text(toma, "xNome", cliente.razao_social or "")

    if cliente.email:
        _sub_text(toma, "email", cliente.email)


def _adicionar_servico(parent: etree._Element, nota) -> None:
    """Adiciona dados do serviço prestado."""
    serv = etree.SubElement(parent, f"{NS}serv")

    _sub_text(serv, "cServ", nota.servico.codigo_lc116)
    _sub_text(serv, "xDescServ", nota.discriminacao or "")
    _sub_text(serv, "cMunPrestacao", str(nota.local_prestacao_ibge))


def _adicionar_valores(parent: etree._Element, nota) -> None:
    """Adiciona grupo de valores e tributos."""
    vals = etree.SubElement(parent, f"{NS}valores")

    _sub_decimal(vals, "vServPrest", nota.valor_servicos)
    _sub_decimal(vals, "vDeducao", nota.valor_deducoes)
    _sub_decimal(vals, "vBC", nota.base_calculo)
    _sub_decimal(vals, "pAliqISS", nota.aliquota_iss)
    _sub_decimal(vals, "vISS", nota.valor_iss)
    _sub_text(vals, "tpRetISS", "1" if nota.iss_retido else "2")

    # Retenções federais
    if nota.valor_pis:
        _sub_decimal(vals, "vPIS", nota.valor_pis)
    if nota.valor_cofins:
        _sub_decimal(vals, "vCOFINS", nota.valor_cofins)
    if nota.valor_inss:
        _sub_decimal(vals, "vINSS", nota.valor_inss)
    if nota.valor_ir:
        _sub_decimal(vals, "vIR", nota.valor_ir)
    if nota.valor_csll:
        _sub_decimal(vals, "vCSLL", nota.valor_csll)

    _sub_decimal(vals, "vLiq", nota.valor_liquido)


def _adicionar_ibs_cbs(parent: etree._Element, nota) -> None:
    """Adiciona grupo IBSCBS se houver valores da reforma tributária."""
    valor_cbs = getattr(nota, "valor_cbs", Decimal("0.00")) or Decimal("0.00")
    valor_ibs = getattr(nota, "valor_ibs", Decimal("0.00")) or Decimal("0.00")

    if valor_cbs > 0 or valor_ibs > 0:
        grupo = etree.SubElement(parent, f"{NS}IBSCBS")
        _sub_decimal(grupo, "vCBS", valor_cbs)
        _sub_decimal(grupo, "vIBS", valor_ibs)


def _sub_text(parent: etree._Element, tag: str, texto: str) -> etree._Element:
    """Cria sub-elemento com texto."""
    elem = etree.SubElement(parent, f"{NS}{tag}")
    elem.text = texto
    return elem


def _sub_decimal(
    parent: etree._Element,
    tag: str,
    valor: Decimal | None,
) -> etree._Element:
    """Cria sub-elemento com valor decimal formatado (2 casas)."""
    elem = etree.SubElement(parent, f"{NS}{tag}")
    elem.text = f"{valor or Decimal('0.00'):.2f}"
    return elem
