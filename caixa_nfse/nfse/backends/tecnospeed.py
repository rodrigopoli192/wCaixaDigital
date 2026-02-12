"""
TecnoSpeed backend — integração com API REST TecnoSpeed NFS-e.

Autenticação: Header token_sh (Software House token).
Processamento assíncrono com polling ou callback.
"""

import logging

from caixa_nfse.nfse.backends.base import (
    BaseNFSeBackend,
    ResultadoCancelamento,
    ResultadoConsulta,
    ResultadoEmissao,
)
from caixa_nfse.nfse.backends.gateway_http import GatewayHttpClient

logger = logging.getLogger(__name__)

TECNOSPEED_URLS = {
    "HOMOLOGACAO": "https://nfse-homologacao.tecnospeed.com.br/api/v1",
    "PRODUCAO": "https://nfse.tecnospeed.com.br/api/v1",
}


class TecnoSpeedBackend(BaseNFSeBackend, GatewayHttpClient):
    """TecnoSpeed gateway backend for NFS-e operations."""

    backend_name = "tecnospeed"

    def _base_url(self, config) -> str:
        ambiente = getattr(config, "ambiente", "HOMOLOGACAO")
        return TECNOSPEED_URLS.get(ambiente, TECNOSPEED_URLS["HOMOLOGACAO"])

    def _auth_headers(self, config) -> dict:
        return {"token_sh": config.api_token or ""}

    def _get_config(self, tenant):
        try:
            return tenant.config_nfse
        except Exception:
            return None

    # ── Mapper ────────────────────────────────────────────────

    def _nota_to_tecnospeed_json(self, nota, tenant) -> dict:
        """Convert internal NotaFiscalServico to TecnoSpeed JSON format."""
        tomador = {}
        if nota.cliente:
            c = nota.cliente
            tomador = {
                "cpf_cnpj": c.cpf_cnpj or "",
                "razao_social": c.razao_social or "",
                "email": c.email or "",
                "logradouro": c.logradouro or "",
                "numero": c.numero or "",
                "complemento": c.complemento or "",
                "bairro": c.bairro or "",
                "codigo_municipio_ibge": c.codigo_ibge or "",
                "uf": c.uf or "",
                "cep": c.cep or "",
            }

        prestador_ibge = ""
        if hasattr(tenant, "codigo_ibge"):
            prestador_ibge = tenant.codigo_ibge or ""

        return {
            "tipo_documento": "NFSE",
            "data_emissao": nota.data_emissao.isoformat() if nota.data_emissao else "",
            "competencia": nota.competencia.isoformat() if nota.competencia else "",
            "prestador": {
                "cnpj": tenant.cnpj or "",
                "inscricao_municipal": tenant.inscricao_municipal or "",
                "codigo_municipio_ibge": prestador_ibge,
            },
            "tomador": tomador,
            "servico": {
                "discriminacao": nota.discriminacao or "Serviços prestados",
                "codigo_item_lista_servico": nota.servico.codigo_lc116 if nota.servico else "",
                "codigo_tributacao_municipio": nota.servico.codigo_municipal
                if nota.servico
                else "",
                "valor_servicos": str(nota.valor_servicos or "0"),
                "aliquota_iss": str(nota.aliquota_iss or "0"),
                "iss_retido": nota.iss_retido,
            },
            "valor_total": str(nota.valor_servicos or "0"),
        }

    # ── Interface ─────────────────────────────────────────────

    def emitir(self, nota, tenant) -> ResultadoEmissao:
        config = self._get_config(tenant)
        if not config:
            return ResultadoEmissao(
                sucesso=False,
                mensagem="Configuração NFS-e não encontrada para este tenant",
            )

        payload = self._nota_to_tecnospeed_json(nota, tenant)

        response = self._request(
            "POST",
            "/nfse/enviar",
            config=config,
            tenant=tenant,
            nota=nota,
            json_body=payload,
        )

        if response is None:
            return ResultadoEmissao(
                sucesso=False,
                mensagem="Falha na comunicação com TecnoSpeed",
            )

        data = response.json() if response.text else {}

        if response.status_code in (200, 201, 202):
            situacao = data.get("situacao", "")
            if situacao in ("autorizada", "aut"):
                return ResultadoEmissao(
                    sucesso=True,
                    numero_nfse=data.get("numero_nfse", ""),
                    codigo_verificacao=data.get("codigo_verificacao", ""),
                    protocolo=data.get("protocolo", ""),
                    xml_retorno=data.get("xml", ""),
                    pdf_url=data.get("link_pdf", ""),
                    mensagem="NFS-e autorizada via TecnoSpeed",
                )
            # Async processing
            return ResultadoEmissao(
                sucesso=True,
                protocolo=data.get("protocolo", str(nota.pk)),
                mensagem=f"NFS-e em processamento: {situacao}",
            )

        # Error
        erros = data.get("erros", data.get("mensagens", []))
        if isinstance(erros, str):
            msg_erro = erros
        elif isinstance(erros, list):
            msg_erro = "; ".join(
                e.get("mensagem", str(e)) if isinstance(e, dict) else str(e) for e in erros
            )
        else:
            msg_erro = data.get("mensagem", f"Erro HTTP {response.status_code}")

        return ResultadoEmissao(
            sucesso=False,
            xml_retorno=response.text,
            mensagem=msg_erro,
        )

    def consultar(self, nota, tenant) -> ResultadoConsulta:
        config = self._get_config(tenant)
        if not config:
            return ResultadoConsulta(
                sucesso=False,
                mensagem="Configuração NFS-e não encontrada",
            )

        response = self._request(
            "GET",
            f"/nfse/consultar/{nota.pk}",
            config=config,
            tenant=tenant,
            nota=nota,
        )

        if response is None:
            return ResultadoConsulta(
                sucesso=False,
                mensagem="Falha na comunicação com TecnoSpeed",
            )

        data = response.json() if response.text else {}

        return ResultadoConsulta(
            sucesso=response.is_success,
            status=data.get("situacao", ""),
            xml_retorno=data.get("xml", ""),
            mensagem=data.get("mensagem", ""),
        )

    def cancelar(self, nota, tenant, motivo: str) -> ResultadoCancelamento:
        config = self._get_config(tenant)
        if not config:
            return ResultadoCancelamento(
                sucesso=False,
                mensagem="Configuração NFS-e não encontrada",
            )

        response = self._request(
            "POST",
            "/nfse/cancelar",
            config=config,
            tenant=tenant,
            nota=nota,
            json_body={
                "id": str(nota.pk),
                "motivo_cancelamento": motivo,
            },
        )

        if response is None:
            return ResultadoCancelamento(
                sucesso=False,
                mensagem="Falha na comunicação com TecnoSpeed",
            )

        data = response.json() if response.text else {}

        return ResultadoCancelamento(
            sucesso=response.is_success,
            protocolo=data.get("protocolo", ""),
            mensagem=data.get("mensagem", "Cancelamento processado"),
        )

    def baixar_danfse(self, nota, tenant) -> bytes | None:
        config = self._get_config(tenant)
        if not config:
            return None

        return self._request_bytes(
            "GET",
            f"/nfse/imprimir/{nota.pk}",
            config=config,
            tenant=tenant,
            nota=nota,
        )
