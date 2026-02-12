"""
Serviço de download do DANFSe (Documento Auxiliar da NFS-e).

Encapsula a lógica de download do PDF via API do Portal Nacional
ou de gateways que forneçam URL direta.
"""

import logging

import httpx

logger = logging.getLogger(__name__)


def baixar_danfse_portal(client, chave_acesso: str) -> bytes | None:
    """
    Baixa o PDF do DANFSe pelo cliente da API do Portal Nacional.

    Args:
        client: Instância de PortalNacionalClient.
        chave_acesso: Chave de acesso da NFS-e (50 dígitos).

    Returns:
        Bytes do PDF ou None se não disponível.
    """
    if not chave_acesso:
        logger.warning("Chave de acesso vazia — não é possível baixar DANFSe")
        return None

    return client.baixar_danfse(chave_acesso)


def baixar_danfse_por_url(pdf_url: str, timeout: int = 15) -> bytes | None:
    """
    Baixa PDF do DANFSe a partir de uma URL direta.

    Útil para backends de gateway que fornecem URL do PDF.

    Args:
        pdf_url: URL completa do PDF.
        timeout: Timeout em segundos.

    Returns:
        Bytes do PDF ou None.
    """
    if not pdf_url:
        return None

    try:
        with httpx.Client(timeout=timeout) as http:
            response = http.get(pdf_url)
            if response.status_code == 200:
                return response.content
            logger.warning("DANFSe download falhou: HTTP %d", response.status_code)
            return None
    except Exception:
        logger.exception("Erro ao baixar DANFSe de %s", pdf_url)
        return None
