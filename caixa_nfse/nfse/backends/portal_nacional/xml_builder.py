"""
Construtor de XML DPS (Declaração Prévia de Serviços) no padrão nacional.

Gera o XML da DPS conforme schema XSD v1.01 do Portal Nacional NFS-e,
incluindo dados do prestador, tomador, serviço, valores e tributos.

Ordem dos elementos em infDPS (TCInfDPS v1.01):
  tpAmb → dhEmi → verAplic → serie → nDPS → dCompet → tpEmit →
  [cMotivoEmisTI] → [chNFSeRej] → cLocEmi → [subst] →
  prest → [toma] → [interm] → serv → valores → [IBSCBS]
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from lxml import etree

NSMAP = {
    None: "http://www.sped.fazenda.gov.br/nfse",
}

NS = "{http://www.sped.fazenda.gov.br/nfse}"

VER_APLIC = "wCaixaDigital_1.0"


def construir_dps(nota, tenant) -> etree._Element:
    """
    Constrói o XML da DPS a partir de uma NotaFiscalServico e do Tenant.

    Retorna o elemento raiz <DPS> pronto para assinatura.
    """
    dps = etree.Element(f"{NS}DPS", nsmap=NSMAP, versao="1.01")
    inf_dps = etree.SubElement(dps, f"{NS}infDPS", Id=_gerar_id_dps(nota, tenant))

    _adicionar_identificacao(inf_dps, nota, tenant)
    _adicionar_prestador(inf_dps, tenant)
    _adicionar_tomador(inf_dps, nota)
    _adicionar_servico(inf_dps, nota)
    _adicionar_valores(inf_dps, nota)

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
    """
    Gera o ID da DPS no formato TSIdDPS: DPS + 42 dígitos numéricos.

    Formato: DPS + cMunEmi(7) + tpInscFed(1) + cpfCnpj(14) + série(5) + nDPS(15)
    """
    cnpj = _limpar_doc(tenant.cnpj)
    cmun = str(nota.local_prestacao_ibge).zfill(7)
    tp_insc = "2" if len(cnpj) == 14 else "1"
    cpf_cnpj = cnpj.zfill(14)
    serie = str(getattr(nota, "serie_rps", 1) or 1).zfill(5)
    numero = str(nota.numero_rps).zfill(15)
    return f"DPS{cmun}{tp_insc}{cpf_cnpj}{serie}{numero}"


# ---------------------------------------------------------------------------
# Blocos de construção (na ordem do schema XSD v1.01)
# ---------------------------------------------------------------------------


def _adicionar_identificacao(parent: etree._Element, nota, tenant) -> None:
    """Campos de identificação em infDPS na ordem do XSD v1.01."""
    _sub_text(parent, "tpAmb", "1" if nota.ambiente == "PRODUCAO" else "2")
    # TSDateTimeUTC: AAAA-MM-DDThh:mm:ssTZD
    # Margem de -5min para compensar diferença de relógio com o servidor
    BRT = timezone(timedelta(hours=-3))
    dt_emissao = (datetime.now(tz=BRT) - timedelta(minutes=5)).isoformat(timespec="seconds")
    _sub_text(parent, "dhEmi", dt_emissao)
    _sub_text(parent, "verAplic", VER_APLIC)
    _sub_text(parent, "serie", str(getattr(nota, "serie_rps", 1) or 1).zfill(5))
    # TSNumDPS: pattern [1-9]{1}[0-9]{0,14} — sem zero-padding
    _sub_text(parent, "nDPS", str(nota.numero_rps))
    _sub_text(parent, "dCompet", str(nota.competencia))
    _sub_text(parent, "tpEmit", "1")  # 1=Prestador
    _sub_text(parent, "cLocEmi", str(nota.local_prestacao_ibge).zfill(7))


def _adicionar_prestador(parent: etree._Element, tenant) -> None:
    """Grupo prest (TCInfoPrestador): choice(CNPJ|CPF) + [IM] + [xNome] + [end] + regTrib."""
    prest = etree.SubElement(parent, f"{NS}prest")

    cnpj = _limpar_doc(tenant.cnpj)
    _sub_text(prest, "CNPJ", cnpj)

    im = getattr(tenant, "inscricao_municipal", None) or ""
    if im:
        _sub_text(prest, "IM", im)

    _sub_text(prest, "xNome", tenant.razao_social or "")

    # Endereço (TCEndereco): choice(endNac|endExt) + xLgr + nro + [xCpl] + xBairro
    end = etree.SubElement(prest, f"{NS}end")
    end_nac = etree.SubElement(end, f"{NS}endNac")
    _sub_text(end_nac, "cMun", str(getattr(tenant, "cod_ibge", "3550308") or "3550308"))
    _sub_text(end_nac, "CEP", (tenant.cep or "").replace("-", ""))
    _sub_text(end, "xLgr", tenant.logradouro or "")
    _sub_text(end, "nro", tenant.numero or "S/N")
    _sub_text(end, "xBairro", tenant.bairro or "")

    # regTrib (TCRegTrib) - obrigatório: opSimpNac + regEspTrib
    reg_trib = etree.SubElement(prest, f"{NS}regTrib")
    _sub_text(reg_trib, "opSimpNac", str(getattr(tenant, "opcao_simples", 1) or 1))
    _sub_text(reg_trib, "regEspTrib", str(getattr(tenant, "regime_especial", 0) or 0))


def _adicionar_tomador(parent: etree._Element, nota) -> None:
    """Grupo toma (TCInfoPessoa): choice(CNPJ|CPF|NIF|cNaoNIF) + xNome + [end] + [email].

    Só adiciona se o cliente tiver CPF ou CNPJ válido.
    O campo toma é opcional no schema (minOccurs=0).
    """
    cliente = nota.cliente
    doc = _limpar_doc(cliente.cpf_cnpj)

    # Se não tem documento, omitir tomador
    if not doc or len(doc) not in (11, 14):
        return

    toma = etree.SubElement(parent, f"{NS}toma")

    if len(doc) == 14:
        _sub_text(toma, "CNPJ", doc)
    else:
        _sub_text(toma, "CPF", doc)

    _sub_text(toma, "xNome", cliente.razao_social or "")

    if cliente.email:
        _sub_text(toma, "email", cliente.email)


def _adicionar_servico(parent: etree._Element, nota) -> None:
    """
    Grupo serv (TCServ):
      locPrest (TCLocPrest) → cServ (TCCServ) → [comExt] → [obra] → [atvEvento] → [infoCompl]
    """
    serv = etree.SubElement(parent, f"{NS}serv")

    # locPrest: choice(cLocPrestacao | cPaisPrestacao)
    loc_prest = etree.SubElement(serv, f"{NS}locPrest")
    _sub_text(loc_prest, "cLocPrestacao", str(nota.local_prestacao_ibge).zfill(7))

    # cServ (TCCServ): cTribNac + [cTribMun] + xDescServ + [cNBS] + [cIntContrib]
    c_serv = etree.SubElement(serv, f"{NS}cServ")
    # cTribNac: 6 dígitos (2 item LC116 + 2 subitem + 2 desdobro)
    codigo_lc116 = nota.servico.codigo_lc116 or ""
    # Normaliza para formato 6 dígitos (ex: "14.01" → "140100")
    c_trib_nac = _normalizar_codigo_trib_nac(codigo_lc116)
    _sub_text(c_serv, "cTribNac", c_trib_nac)
    _sub_text(c_serv, "xDescServ", nota.discriminacao or "")


def _adicionar_valores(parent: etree._Element, nota) -> None:
    """
    Grupo valores (TCInfoValores):
      vServPrest (TCVServPrest) → [vDescCondIncond] → [vDedRed] → trib (TCInfoTributacao)
    """
    vals = etree.SubElement(parent, f"{NS}valores")

    # vServPrest (TCVServPrest): [vReceb] + vServ
    v_serv_prest = etree.SubElement(vals, f"{NS}vServPrest")
    _sub_decimal(v_serv_prest, "vServ", nota.valor_servicos)

    # trib (TCInfoTributacao): tribMun + [tribFed] + totTrib
    trib = etree.SubElement(vals, f"{NS}trib")

    # tribMun (TCTribMunicipal): tribISSQN + [cPaisResult] + [tpImunidade] +
    #   [exigSusp] + [BM] + tpRetISSQN + [pAliq]
    trib_mun = etree.SubElement(trib, f"{NS}tribMun")
    _sub_text(trib_mun, "tribISSQN", "1")  # 1=Operação tributável
    _sub_text(trib_mun, "tpRetISSQN", "2" if nota.iss_retido else "1")  # 1=Não retido, 2=Retido
    if nota.aliquota_iss:
        _sub_decimal(trib_mun, "pAliq", nota.aliquota_iss)

    # totTrib (TCTribTotal): choice(vTotTrib | pTotTrib | indTotTrib | pTotTribSN)
    tot_trib = etree.SubElement(trib, f"{NS}totTrib")
    _sub_text(tot_trib, "indTotTrib", "0")  # 0=Não informar


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _limpar_doc(doc: str | None) -> str:
    """Remove pontuação de CNPJ/CPF."""
    return (doc or "").replace(".", "").replace("/", "").replace("-", "")


def _normalizar_codigo_trib_nac(codigo: str) -> str:
    """
    Converte código LC116 (ex: '14.01', '1401') para formato cTribNac de 6 dígitos.

    Formato: IISSDD (2 dígitos item + 2 dígitos subitem + 2 dígitos desdobro).
    """
    limpo = codigo.replace(".", "").replace("-", "").replace(" ", "")
    # Se tem 4 dígitos (ex: "1401"), adiciona "01" de desdobro (padrão nacional)
    if len(limpo) == 4:
        return limpo + "01"
    # Se tem 6 dígitos, já está no formato correto
    if len(limpo) == 6:
        return limpo
    # Fallback: preenche com zeros à direita
    return limpo.ljust(6, "0")[:6]


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
