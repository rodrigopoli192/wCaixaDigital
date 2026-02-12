"""
Focus NFe backend — integração com API REST v2 da Focus NFe.

Autenticação: HTTP Basic Auth (api_token como username, senha vazia).
Processamento assíncrono: emissão retorna status intermediário.
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

FOCUS_URLS = {
    "HOMOLOGACAO": "https://homologacao.focusnfe.com.br/v2",
    "PRODUCAO": "https://api.focusnfe.com.br/v2",
}


class FocusNFeBackend(BaseNFSeBackend, GatewayHttpClient):
    """Focus NFe gateway backend for NFS-e operations."""

    backend_name = "focus_nfe"

    def _base_url(self, config) -> str:
        ambiente = getattr(config, "ambiente", "HOMOLOGACAO")
        return FOCUS_URLS.get(ambiente, FOCUS_URLS["HOMOLOGACAO"])

    def _auth_headers(self, config) -> dict:
        import base64

        token = config.api_token or ""
        credentials = base64.b64encode(f"{token}:".encode()).decode()
        return {"Authorization": f"Basic {credentials}"}

    def _get_config(self, tenant):
        try:
            return tenant.config_nfse
        except Exception:
            return None

    # ── Mapper ────────────────────────────────────────────────

    def _nota_to_focus_json(self, nota, tenant) -> dict:
        """Convert internal NotaFiscalServico to Focus NFe JSON format."""
        tomador = {}
        if nota.cliente:
            c = nota.cliente
            tomador = {
                "cpf_cnpj": c.cpf_cnpj or "",
                "razao_social": c.razao_social or "",
                "email": c.email or "",
                "endereco": c.logradouro or "",
                "numero": c.numero or "",
                "complemento": c.complemento or "",
                "bairro": c.bairro or "",
                "codigo_municipio": c.codigo_ibge or "",
                "uf": c.uf or "",
                "cep": c.cep or "",
            }

        prestador_ibge = ""
        if hasattr(tenant, "codigo_ibge"):
            prestador_ibge = tenant.codigo_ibge or ""

        return {
            "data_emissao": nota.data_emissao.isoformat() if nota.data_emissao else "",
            "natureza_operacao": "1",  # Tributação no município
            "prestador": {
                "cnpj": tenant.cnpj or "",
                "inscricao_municipal": tenant.inscricao_municipal or "",
                "codigo_municipio": prestador_ibge,
            },
            "tomador": tomador,
            "servico": {
                "discriminacao": nota.discriminacao or "Serviços prestados",
                "aliquota": str(nota.aliquota_iss or "0"),
                "valor_servicos": str(nota.valor_servicos or "0"),
                "iss_retido": "true" if nota.iss_retido else "false",
                "item_lista_servico": nota.servico.codigo_lc116 if nota.servico else "",
                "codigo_tributario_municipio": nota.servico.codigo_municipal
                if nota.servico
                else "",
            },
        }

    # ── Interface ─────────────────────────────────────────────

    def emitir(self, nota, tenant) -> ResultadoEmissao:
        config = self._get_config(tenant)
        if not config:
            return ResultadoEmissao(
                sucesso=False,
                mensagem="Configuração NFS-e não encontrada para este tenant",
            )

        ref = str(nota.pk)
        payload = self._nota_to_focus_json(nota, tenant)

        response = self._request(
            "POST",
            f"/nfse?ref={ref}",
            config=config,
            tenant=tenant,
            nota=nota,
            json_body=payload,
        )

        if response is None:
            return ResultadoEmissao(
                sucesso=False,
                mensagem="Falha na comunicação com Focus NFe",
            )

        data = response.json() if response.text else {}

        if response.status_code in (200, 201, 202):
            status = data.get("status", "")
            if status in ("autorizado", "autorizada"):
                return ResultadoEmissao(
                    sucesso=True,
                    numero_nfse=data.get("numero", ""),
                    codigo_verificacao=data.get("codigo_verificacao", ""),
                    protocolo=data.get("protocolo", ""),
                    xml_retorno=data.get("xml_nfse", ""),
                    pdf_url=data.get("caminho_xml_nota_fiscal", ""),
                    mensagem="NFS-e autorizada via Focus NFe",
                )
            # Processing (async)
            return ResultadoEmissao(
                sucesso=True,
                protocolo=data.get("protocolo", ref),
                mensagem=f"NFS-e em processamento: {status}",
            )

        # Error
        erros = data.get("erros", [])
        msg_erro = (
            "; ".join(e.get("mensagem", str(e)) if isinstance(e, dict) else str(e) for e in erros)
            if erros
            else data.get("mensagem", f"Erro HTTP {response.status_code}")
        )

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

        ref = str(nota.pk)
        response = self._request(
            "GET",
            f"/nfse/{ref}",
            config=config,
            tenant=tenant,
            nota=nota,
        )

        if response is None:
            return ResultadoConsulta(
                sucesso=False,
                mensagem="Falha na comunicação com Focus NFe",
            )

        data = response.json() if response.text else {}

        return ResultadoConsulta(
            sucesso=response.is_success,
            status=data.get("status", ""),
            xml_retorno=data.get("xml_nfse", ""),
            mensagem=data.get("mensagem", ""),
        )

    def cancelar(self, nota, tenant, motivo: str) -> ResultadoCancelamento:
        config = self._get_config(tenant)
        if not config:
            return ResultadoCancelamento(
                sucesso=False,
                mensagem="Configuração NFS-e não encontrada",
            )

        ref = str(nota.pk)
        response = self._request(
            "DELETE",
            f"/nfse/{ref}",
            config=config,
            tenant=tenant,
            nota=nota,
            json_body={"justificativa": motivo},
        )

        if response is None:
            return ResultadoCancelamento(
                sucesso=False,
                mensagem="Falha na comunicação com Focus NFe",
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

        ref = str(nota.pk)
        return self._request_bytes(
            "GET",
            f"/nfse/{ref}.pdf",
            config=config,
            tenant=tenant,
            nota=nota,
        )
