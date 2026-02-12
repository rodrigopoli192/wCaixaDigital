"""
Backend do Portal Nacional NFS-e — integração direta com a API REST.

Fluxo de emissão:
1. Construir XML DPS (xml_builder)
2. Assinar XML com certificado A1 (xml_signer)
3. Enviar DPS compactada via API REST (api_client)
4. Processar resposta e atualizar nota
"""

import logging

from caixa_nfse.nfse.backends.base import (
    BaseNFSeBackend,
    ResultadoCancelamento,
    ResultadoConsulta,
    ResultadoEmissao,
)
from caixa_nfse.nfse.backends.portal_nacional.api_client import PortalNacionalClient
from caixa_nfse.nfse.backends.portal_nacional.danfse import baixar_danfse_portal
from caixa_nfse.nfse.backends.portal_nacional.xml_builder import (
    construir_dps,
    dps_para_string,
)
from caixa_nfse.nfse.backends.portal_nacional.xml_signer import assinar_xml

logger = logging.getLogger(__name__)


class PortalNacionalBackend(BaseNFSeBackend):
    """
    Implementação do backend via integração direta com o Portal Nacional NFS-e.

    Utiliza certificado digital A1 do tenant para assinatura e autenticação mTLS.
    """

    def emitir(self, nota, tenant) -> ResultadoEmissao:
        """
        Emite NFS-e: constrói DPS → assina → envia ao Portal Nacional.
        """
        try:
            # 1. Construir XML DPS
            dps_element = construir_dps(nota, tenant)

            # 2. Assinar XML
            certificado_bytes = _obter_certificado(tenant)
            if certificado_bytes is None:
                return ResultadoEmissao(
                    sucesso=False,
                    mensagem="Certificado digital A1 não configurado para este tenant",
                )

            dps_assinado = assinar_xml(
                dps_element,
                certificado_bytes,
                tenant.certificado_senha or "",
            )
            xml_assinado = dps_para_string(dps_assinado)

            # 3. Enviar ao Portal Nacional
            client = _criar_client(nota, tenant)
            resposta = client.enviar_dps(xml_assinado)

            if not resposta.sucesso:
                return ResultadoEmissao(
                    sucesso=False,
                    mensagem=resposta.mensagem or f"Erro HTTP {resposta.status_code}",
                    xml_retorno=resposta.xml_retorno,
                )

            # 4. Processar resposta de sucesso
            dados = resposta.dados or {}
            return ResultadoEmissao(
                sucesso=True,
                numero_nfse=dados.get("nNFSe"),
                chave_acesso=dados.get("chNFSe", ""),
                codigo_verificacao=dados.get("cVerif", ""),
                protocolo=dados.get("nProt", ""),
                xml_retorno=resposta.xml_retorno,
                pdf_url=dados.get("urlDanfse", ""),
                mensagem="NFS-e emitida com sucesso via Portal Nacional",
            )

        except ValueError as e:
            logger.error("Erro de validação na emissão: %s", e)
            return ResultadoEmissao(sucesso=False, mensagem=str(e))

        except Exception as e:
            logger.exception("Erro inesperado na emissão via Portal Nacional")
            return ResultadoEmissao(
                sucesso=False,
                mensagem=f"Erro inesperado: {e}",
            )

    def consultar(self, nota, tenant) -> ResultadoConsulta:
        """Consulta status da NFS-e no Portal Nacional."""
        try:
            client = _criar_client(nota, tenant)

            # Prefere consulta por chave de acesso
            if nota.chave_acesso:
                resposta = client.consultar_por_chave(nota.chave_acesso)
            elif nota.id_dps:
                resposta = client.consultar_por_dps(nota.id_dps)
            else:
                return ResultadoConsulta(
                    sucesso=False,
                    mensagem="Sem chave de acesso ou ID da DPS para consulta",
                )

            if not resposta.sucesso:
                return ResultadoConsulta(
                    sucesso=False,
                    mensagem=resposta.mensagem,
                )

            dados = resposta.dados or {}
            return ResultadoConsulta(
                sucesso=True,
                status=dados.get("sit", ""),
                xml_retorno=resposta.xml_retorno,
                mensagem="Consulta realizada com sucesso",
            )

        except Exception as e:
            logger.exception("Erro ao consultar NFS-e no Portal Nacional")
            return ResultadoConsulta(sucesso=False, mensagem=str(e))

    def cancelar(self, nota, tenant, motivo: str) -> ResultadoCancelamento:
        """Solicita cancelamento da NFS-e no Portal Nacional."""
        try:
            if not nota.chave_acesso:
                return ResultadoCancelamento(
                    sucesso=False,
                    mensagem="Chave de acesso não disponível para cancelamento",
                )

            client = _criar_client(nota, tenant)
            resposta = client.cancelar(nota.chave_acesso, motivo)

            if not resposta.sucesso:
                return ResultadoCancelamento(
                    sucesso=False,
                    mensagem=resposta.mensagem,
                )

            dados = resposta.dados or {}
            return ResultadoCancelamento(
                sucesso=True,
                protocolo=dados.get("nProt", ""),
                mensagem="NFS-e cancelada com sucesso via Portal Nacional",
            )

        except Exception as e:
            logger.exception("Erro ao cancelar NFS-e no Portal Nacional")
            return ResultadoCancelamento(sucesso=False, mensagem=str(e))

    def baixar_danfse(self, nota, tenant) -> bytes | None:
        """Baixa o PDF do DANFSe via Portal Nacional."""
        if not nota.chave_acesso:
            return None

        client = _criar_client(nota, tenant)
        return baixar_danfse_portal(client, nota.chave_acesso)


def _obter_certificado(tenant) -> bytes | None:
    """Obtém bytes do certificado digital A1 do tenant."""
    if hasattr(tenant, "certificado_digital") and tenant.certificado_digital:
        try:
            return tenant.certificado_digital.read()
        except Exception:
            logger.warning("Não foi possível ler certificado do tenant %s", tenant)
    return None


def _criar_client(nota, tenant) -> PortalNacionalClient:
    """Cria instância do client HTTP configurada para o ambiente da nota."""
    return PortalNacionalClient(
        ambiente=nota.ambiente or "HOMOLOGACAO",
    )
