"""
Cliente HTTP para a API REST do Portal Nacional NFS-e.

Endpoints:
- Produção: https://sefin.nfse.gov.br/sefinnacional
- Homologação: https://sefin.producaorestrita.nfse.gov.br/sefinnacional

Todas as requisições enviam o XML da DPS compactado em GZip e codificado em Base64.
A autenticação mTLS usa o certificado digital A1 (.pfx/.p12) do tenant.
"""

import base64
import gzip
import logging
import tempfile
from dataclasses import dataclass

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12

logger = logging.getLogger(__name__)

URLS = {
    "PRODUCAO": "https://sefin.nfse.gov.br/sefinnacional",
    "HOMOLOGACAO": "https://sefin.producaorestrita.nfse.gov.br/sefinnacional",
}

TIMEOUT_SEGUNDOS = 30


@dataclass
class RespostaAPI:
    """Resposta padronizada da API do Portal Nacional."""

    sucesso: bool
    status_code: int
    dados: dict | None = None
    mensagem: str = ""
    xml_retorno: str = ""


class PortalNacionalClient:
    """
    Cliente HTTP para comunicação com a API REST do Portal Nacional NFS-e.

    Utiliza certificado digital A1 para autenticação mTLS.
    Aceita certificado PKCS#12 em bytes (do BinaryField) ou paths de arquivo PEM.
    """

    def __init__(
        self,
        ambiente: str = "HOMOLOGACAO",
        certificado_bytes: bytes | None = None,
        certificado_senha: str | None = None,
        timeout: int = TIMEOUT_SEGUNDOS,
    ):
        self.base_url = URLS.get(ambiente, URLS["HOMOLOGACAO"])
        self.timeout = timeout
        self._cert_config = None
        self._temp_files: list = []

        if certificado_bytes and certificado_senha:
            self._cert_config = self._extrair_pem(certificado_bytes, certificado_senha)

    def _extrair_pem(self, pfx_bytes: bytes, senha: str) -> tuple[str, str] | None:
        """Extrai cert e key PEM do PKCS#12 para temp files usados pelo httpx mTLS."""
        try:
            chave, cert, cadeia = pkcs12.load_key_and_certificates(pfx_bytes, senha.encode("utf-8"))
            if not chave or not cert:
                logger.error("Certificado PKCS#12 sem chave privada ou certificado")
                return None

            # Salvar cert PEM
            cert_pem = cert.public_bytes(serialization.Encoding.PEM)
            if cadeia:
                for ca in cadeia:
                    cert_pem += ca.public_bytes(serialization.Encoding.PEM)

            cert_file = tempfile.NamedTemporaryFile(
                suffix=".pem", prefix="nfse_cert_", delete=False
            )
            cert_file.write(cert_pem)
            cert_file.flush()
            self._temp_files.append(cert_file)

            # Salvar key PEM
            key_pem = chave.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
            key_file = tempfile.NamedTemporaryFile(suffix=".pem", prefix="nfse_key_", delete=False)
            key_file.write(key_pem)
            key_file.flush()
            self._temp_files.append(key_file)

            return (cert_file.name, key_file.name)

        except Exception:
            logger.exception("Erro ao extrair PEM do PKCS#12")
            return None

    def __del__(self):
        """Remove temp files de cert/key PEM."""
        import os

        for f in self._temp_files:
            try:
                os.unlink(f.name)
            except OSError:
                pass

    def enviar_dps(self, xml_assinado: str) -> RespostaAPI:
        """
        Envia DPS assinada ao Portal Nacional para geração síncrona da NFS-e.

        O XML é compactado com GZip e codificado em Base64 antes do envio.
        """
        xml_compactado = _compactar_xml(xml_assinado)

        payload = {
            "dpsXmlGZipB64": xml_compactado,
        }

        return self._post("/nfse", json=payload)

    def consultar_por_chave(self, chave_acesso: str) -> RespostaAPI:
        """Consulta uma NFS-e pela chave de acesso."""
        return self._get(f"/nfse/{chave_acesso}")

    def consultar_por_dps(self, id_dps: str) -> RespostaAPI:
        """Consulta uma NFS-e pelo ID da DPS."""
        return self._get(f"/nfse/dps/{id_dps}")

    def cancelar(self, chave_acesso: str, motivo: str) -> RespostaAPI:
        """Solicita cancelamento de uma NFS-e autorizada."""
        payload = {
            "chNFSe": chave_acesso,
            "xMotivo": motivo,
        }
        return self._post(f"/nfse/{chave_acesso}/cancelar", json=payload)

    def baixar_danfse(self, chave_acesso: str) -> bytes | None:
        """Baixa o PDF do DANFSe. Retorna bytes ou None."""
        try:
            response = self._request("GET", f"/danfse/{chave_acesso}")
            if response.sucesso and response.dados:
                pdf_b64 = response.dados.get("pdf", "")
                if pdf_b64:
                    return base64.b64decode(pdf_b64)
            return None
        except Exception:
            logger.exception("Erro ao baixar DANFSe para chave %s", chave_acesso)
            return None

    def _post(self, endpoint: str, **kwargs) -> RespostaAPI:
        """Requisição POST."""
        return self._request("POST", endpoint, **kwargs)

    def _get(self, endpoint: str) -> RespostaAPI:
        """Requisição GET."""
        return self._request("GET", endpoint)

    def _request(self, method: str, endpoint: str, **kwargs) -> RespostaAPI:
        """Executa requisição HTTP com tratamento de erros."""
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        try:
            with httpx.Client(
                timeout=self.timeout,
                cert=self._cert_config,
                verify=True,
            ) as client:
                response = client.request(method, url, headers=headers, **kwargs)

            dados = None
            xml_retorno = ""

            if response.headers.get("content-type", "").startswith("application/json"):
                dados = response.json()
                xml_retorno = dados.get("nfseXmlGZipB64", "")
                if xml_retorno:
                    xml_retorno = _descompactar_xml(xml_retorno)

            sucesso = 200 <= response.status_code < 300
            mensagem = ""
            if dados and not sucesso:
                mensagem = dados.get("mensagem", dados.get("message", str(dados)))

            return RespostaAPI(
                sucesso=sucesso,
                status_code=response.status_code,
                dados=dados,
                mensagem=mensagem,
                xml_retorno=xml_retorno,
            )

        except httpx.TimeoutException:
            logger.error("Timeout na requisição %s %s", method, url)
            return RespostaAPI(
                sucesso=False,
                status_code=0,
                mensagem="Timeout na comunicação com o Portal Nacional",
            )

        except httpx.HTTPError as e:
            logger.error("Erro HTTP na requisição %s %s: %s", method, url, e)
            return RespostaAPI(
                sucesso=False,
                status_code=0,
                mensagem=f"Erro de comunicação: {e}",
            )


def _compactar_xml(xml_string: str) -> str:
    """Compacta XML com GZip e codifica em Base64."""
    xml_bytes = xml_string.encode("utf-8")
    compactado = gzip.compress(xml_bytes)
    return base64.b64encode(compactado).decode("ascii")


def _descompactar_xml(b64_string: str) -> str:
    """Decodifica Base64 e descompacta GZip para obter XML."""
    try:
        compactado = base64.b64decode(b64_string)
        return gzip.decompress(compactado).decode("utf-8")
    except Exception:
        logger.warning("Falha ao descompactar XML de retorno, retornando raw")
        return b64_string
