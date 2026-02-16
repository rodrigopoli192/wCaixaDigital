"""
Testes do api_client — Cliente HTTP para API REST do Portal Nacional.
"""

import base64
import gzip
from unittest.mock import MagicMock, patch

import httpx

from caixa_nfse.nfse.backends.portal_nacional.api_client import (
    URLS,
    PortalNacionalClient,
    RespostaAPI,
    _compactar_xml,
    _descompactar_xml,
)


class TestCompactacao:
    def test_compactar_xml(self):
        """XML compactado em GZip+Base64 deve ser decodificável."""
        xml = "<nota>teste</nota>"
        resultado = _compactar_xml(xml)
        assert isinstance(resultado, str)
        # Decodifica: Base64 → GZip → XML
        decompressed = gzip.decompress(base64.b64decode(resultado))
        assert decompressed.decode("utf-8") == xml

    def test_descompactar_xml(self):
        """Deve descompactar GZip+Base64 para XML."""
        xml_original = "<nota>retorno</nota>"
        compactado = base64.b64encode(gzip.compress(xml_original.encode())).decode()
        resultado = _descompactar_xml(compactado)
        assert resultado == xml_original

    def test_descompactar_invalido_retorna_raw(self):
        """Se dados inválidos, retorna o valor original sem erro."""
        resultado = _descompactar_xml("dados_invalidos")
        assert resultado == "dados_invalidos"

    def test_roundtrip_compactar_descompactar(self):
        """Compactar e descompactar devem ser inversos."""
        xml = '<?xml version="1.0"?><DPS><infDPS Id="TESTE"/></DPS>'
        compactado = _compactar_xml(xml)
        restaurado = _descompactar_xml(compactado)
        assert restaurado == xml


class TestPortalNacionalClient:
    def test_url_producao(self):
        """Cliente em produção deve apontar para URL correta."""
        client = PortalNacionalClient(ambiente="PRODUCAO")
        assert client.base_url == URLS["PRODUCAO"]

    def test_url_homologacao(self):
        """Cliente em homologação deve apontar para URL correta."""
        client = PortalNacionalClient(ambiente="HOMOLOGACAO")
        assert client.base_url == URLS["HOMOLOGACAO"]

    def test_url_desconhecido_fallback_homologacao(self):
        """Ambiente desconhecido deve usar homologação como fallback."""
        client = PortalNacionalClient(ambiente="INVALIDO")
        assert client.base_url == URLS["HOMOLOGACAO"]

    @patch("caixa_nfse.nfse.backends.portal_nacional.api_client.httpx.Client")
    def test_enviar_dps_sucesso(self, mock_client_cls):
        """Envio bem-sucedido deve retornar sucesso=True com dados."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {
            "nNFSe": "12345",
            "chNFSe": "CHAVE50DIGITOS" + "0" * 36,
            "nProt": "PROT123",
        }

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = mock_response
        mock_client_cls.return_value = mock_client

        client = PortalNacionalClient()
        resposta = client.enviar_dps("<DPS/>")

        assert resposta.sucesso is True
        assert resposta.status_code == 200
        assert resposta.dados["nNFSe"] == "12345"

    @patch("caixa_nfse.nfse.backends.portal_nacional.api_client.httpx.Client")
    def test_enviar_dps_rejeicao(self, mock_client_cls):
        """Rejeição (422) deve retornar sucesso=False com mensagem."""
        mock_response = MagicMock()
        mock_response.status_code = 422
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {
            "mensagem": "DPS inválida: campo obrigatório ausente",
        }

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = mock_response
        mock_client_cls.return_value = mock_client

        client = PortalNacionalClient()
        resposta = client.enviar_dps("<DPS/>")

        assert resposta.sucesso is False
        assert "inválida" in resposta.mensagem

    @patch("caixa_nfse.nfse.backends.portal_nacional.api_client.httpx.Client")
    def test_timeout_retorna_erro(self, mock_client_cls):
        """Timeout deve retornar sucesso=False com mensagem descritiva."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.side_effect = httpx.TimeoutException("timeout")
        mock_client_cls.return_value = mock_client

        client = PortalNacionalClient()
        resposta = client.enviar_dps("<DPS/>")

        assert resposta.sucesso is False
        assert resposta.status_code == 0
        assert "Timeout" in resposta.mensagem

    @patch("caixa_nfse.nfse.backends.portal_nacional.api_client.httpx.Client")
    def test_erro_http_retorna_erro(self, mock_client_cls):
        """Erro de rede deve retornar sucesso=False."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.side_effect = httpx.ConnectError("sem conexão")
        mock_client_cls.return_value = mock_client

        client = PortalNacionalClient()
        resposta = client.enviar_dps("<DPS/>")

        assert resposta.sucesso is False
        assert "comunicação" in resposta.mensagem.lower()

    @patch("caixa_nfse.nfse.backends.portal_nacional.api_client.httpx.Client")
    def test_consultar_por_chave(self, mock_client_cls):
        """Consulta por chave deve chamar GET no endpoint correto."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {"sit": "AUTORIZADA"}

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = mock_response
        mock_client_cls.return_value = mock_client

        client = PortalNacionalClient()
        resposta = client.consultar_por_chave("CHAVE123")

        assert resposta.sucesso is True
        mock_client.request.assert_called_once()
        call_args = mock_client.request.call_args
        assert "/nfse/CHAVE123" in call_args[0][1]

    @patch("caixa_nfse.nfse.backends.portal_nacional.api_client.httpx.Client")
    def test_consultar_por_dps(self, mock_client_cls):
        """Consulta por ID DPS deve chamar GET no endpoint correto."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {"sit": "AUTORIZADA"}

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = mock_response
        mock_client_cls.return_value = mock_client

        client = PortalNacionalClient()
        resposta = client.consultar_por_dps("DPS123")

        assert resposta.sucesso is True
        call_url = mock_client.request.call_args[0][1]
        assert "/nfse/dps/DPS123" in call_url

    @patch("caixa_nfse.nfse.backends.portal_nacional.api_client.httpx.Client")
    def test_cancelar_sucesso(self, mock_client_cls):
        """Cancelamento bem-sucedido deve retornar sucesso=True."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {"nProt": "CANCEL123"}

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = mock_response
        mock_client_cls.return_value = mock_client

        client = PortalNacionalClient()
        resposta = client.cancelar("CHAVE123", "Erro de preenchimento")

        assert resposta.sucesso is True

    @patch("caixa_nfse.nfse.backends.portal_nacional.api_client.httpx.Client")
    def test_baixar_danfse_sucesso(self, mock_client_cls):
        """Download do DANFSe deve retornar bytes do PDF."""
        pdf_content = b"%PDF-1.4 conteudo_teste"
        pdf_b64 = base64.b64encode(pdf_content).decode()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {"pdf": pdf_b64}

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = mock_response
        mock_client_cls.return_value = mock_client

        client = PortalNacionalClient()
        resultado = client.baixar_danfse("CHAVE123")

        assert resultado == pdf_content

    @patch("caixa_nfse.nfse.backends.portal_nacional.api_client.httpx.Client")
    def test_baixar_danfse_sem_pdf(self, mock_client_cls):
        """Se resposta não tiver PDF, retorna None."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {}

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = mock_response
        mock_client_cls.return_value = mock_client

        client = PortalNacionalClient()
        resultado = client.baixar_danfse("CHAVE123")

        assert resultado is None

    @patch("caixa_nfse.nfse.backends.portal_nacional.api_client.httpx.Client")
    def test_baixar_danfse_erro_retorna_none(self, mock_client_cls):
        """Erro no download deve retornar None sem levantar exceção."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.side_effect = Exception("erro")
        mock_client_cls.return_value = mock_client

        client = PortalNacionalClient()
        resultado = client.baixar_danfse("CHAVE123")

        assert resultado is None

    @patch("caixa_nfse.nfse.backends.portal_nacional.api_client.httpx.Client")
    def test_resposta_com_xml_compactado(self, mock_client_cls):
        """XML de retorno compactado em GZip+Base64 deve ser descompactado."""
        xml_retorno = "<nfse>autorizada</nfse>"
        xml_compactado = base64.b64encode(gzip.compress(xml_retorno.encode())).decode()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {"nfseXmlGZipB64": xml_compactado}

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.request.return_value = mock_response
        mock_client_cls.return_value = mock_client

        client = PortalNacionalClient()
        resposta = client.enviar_dps("<DPS/>")

        assert resposta.xml_retorno == xml_retorno

    def test_cert_config_quando_fornecido(self):
        """Deve configurar certificado para mTLS quando fornecido."""
        with patch.object(
            PortalNacionalClient,
            "_extrair_pem",
            return_value=("/tmp/cert.pem", "/tmp/key.pem"),
        ):
            client = PortalNacionalClient(
                certificado_bytes=b"fake-pfx-bytes",
                certificado_senha="senha",
            )
            assert client._cert_config == ("/tmp/cert.pem", "/tmp/key.pem")

    def test_cert_config_none_quando_ausente(self):
        """Sem certificado, _cert_config deve ser None."""
        client = PortalNacionalClient()
        assert client._cert_config is None


class TestRespostaAPI:
    def test_defaults(self):
        """RespostaAPI deve ter defaults corretos."""
        resp = RespostaAPI(sucesso=True, status_code=200)
        assert resp.dados is None
        assert resp.mensagem == ""
        assert resp.xml_retorno == ""
