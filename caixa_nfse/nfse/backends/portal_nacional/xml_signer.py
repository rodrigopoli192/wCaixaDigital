"""
Assinatura digital XML (XMLDSIG) para DPS/NFS-e.

Utiliza certificado digital ICP-Brasil tipo A1 (.pfx/.p12)
para assinar o XML da DPS com enveloped signature.
"""

import logging

from cryptography.hazmat.primitives.serialization import pkcs12
from lxml import etree
from signxml import SignatureConstructionMethod, XMLSigner

logger = logging.getLogger(__name__)


def assinar_xml(
    xml_element: etree._Element,
    certificado_bytes: bytes,
    senha: str,
    reference_uri: str | None = None,
) -> etree._Element:
    """
    Assina um elemento XML com certificado A1 (PKCS#12).

    Args:
        xml_element: Elemento XML raiz a ser assinado.
        certificado_bytes: Conteúdo binário do certificado .pfx/.p12.
        senha: Senha do certificado.
        reference_uri: URI de referência para a assinatura (ex: '#DPS...').
            Se None, detecta automaticamente pelo atributo Id.

    Returns:
        Elemento XML assinado com tag <Signature>.

    Raises:
        ValueError: Se o certificado não puder ser carregado.
        signxml.exceptions.InvalidInput: Se o XML for inválido.
    """
    chave_privada, certificado, cadeia = _carregar_certificado(certificado_bytes, senha)

    if reference_uri is None:
        reference_uri = _detectar_reference_uri(xml_element)

    signer = XMLSigner(
        method=SignatureConstructionMethod.enveloped,
        digest_algorithm="sha256",
        signature_algorithm="rsa-sha256",
        c14n_algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315",
    )
    # Portal Nacional rejeita XML com prefixo de namespace (E6155).
    # O signxml usa "ds:" por padrão; forçar namespace default (sem prefixo).
    signer.namespaces = {None: "http://www.w3.org/2000/09/xmldsig#"}

    xml_assinado = signer.sign(
        xml_element,
        key=chave_privada,
        cert=[certificado] + list(cadeia or []),
        reference_uri=reference_uri,
    )

    logger.debug("XML assinado com sucesso (ref: %s)", reference_uri)
    return xml_assinado


def _carregar_certificado(certificado_bytes: bytes, senha: str):
    """
    Carrega certificado PKCS#12 (A1).

    Returns:
        Tupla (chave_privada, certificado, cadeia_certificados).

    Raises:
        ValueError: Se não conseguir carregar o certificado.
    """
    try:
        chave_privada, certificado, cadeia = pkcs12.load_key_and_certificates(
            certificado_bytes,
            senha.encode("utf-8"),
        )
    except Exception as e:
        raise ValueError(f"Erro ao carregar certificado A1: {e}") from e

    if chave_privada is None or certificado is None:
        raise ValueError("Certificado A1 inválido: chave privada ou certificado ausente")

    return chave_privada, certificado, cadeia or []


def _detectar_reference_uri(xml_element: etree._Element) -> str:
    """
    Detecta o URI de referência a partir do atributo 'Id' no XML.

    Percorre os elementos buscando o primeiro que tenha atributo 'Id'.
    """
    for elem in xml_element.iter():
        id_val = elem.get("Id")
        if id_val:
            return f"#{id_val}"

    return ""
