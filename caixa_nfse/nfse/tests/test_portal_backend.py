"""
Testes do PortalNacionalBackend — Fluxo completo emitir/consultar/cancelar.
"""

from unittest.mock import MagicMock, patch

import pytest

from caixa_nfse.nfse.backends.portal_nacional.api_client import RespostaAPI
from caixa_nfse.nfse.backends.portal_nacional.backend import (
    PortalNacionalBackend,
    _obter_certificado,
)
from caixa_nfse.nfse.backends.portal_nacional.danfse import (
    baixar_danfse_por_url,
    baixar_danfse_portal,
)
from caixa_nfse.tests.factories import NotaFiscalServicoFactory


@pytest.mark.django_db
class TestPortalNacionalBackendEmitir:
    def setup_method(self):
        self.backend = PortalNacionalBackend()

    def test_emitir_sem_certificado(self):
        """Sem certificado A1, deve retornar erro."""
        nota = NotaFiscalServicoFactory()
        resultado = self.backend.emitir(nota, nota.tenant)
        assert resultado.sucesso is False
        assert "certificado" in resultado.mensagem.lower()

    @patch("caixa_nfse.nfse.backends.portal_nacional.backend._criar_client")
    @patch("caixa_nfse.nfse.backends.portal_nacional.backend.assinar_xml")
    @patch("caixa_nfse.nfse.backends.portal_nacional.backend._obter_certificado")
    def test_emitir_sucesso(self, mock_cert, mock_assinar, mock_client):
        """Emissão bem-sucedida deve retornar dados da NFS-e."""
        mock_cert.return_value = b"cert_bytes"

        from lxml import etree

        mock_assinar.return_value = etree.fromstring("<DPS/>")

        mock_api = MagicMock()
        mock_api.enviar_dps.return_value = RespostaAPI(
            sucesso=True,
            status_code=200,
            dados={
                "nNFSe": "99999",
                "chNFSe": "CHAVE" + "0" * 45,
                "cVerif": "VERIF123",
                "nProt": "PROT456",
                "urlDanfse": "https://portal.nfse.gov.br/danfse/123",
            },
        )
        mock_client.return_value = mock_api

        nota = NotaFiscalServicoFactory()
        resultado = self.backend.emitir(nota, nota.tenant)

        assert resultado.sucesso is True
        assert resultado.numero_nfse == "99999"
        assert resultado.chave_acesso == "CHAVE" + "0" * 45
        assert resultado.protocolo == "PROT456"
        assert "sucesso" in resultado.mensagem.lower()

    @patch("caixa_nfse.nfse.backends.portal_nacional.backend._criar_client")
    @patch("caixa_nfse.nfse.backends.portal_nacional.backend.assinar_xml")
    @patch("caixa_nfse.nfse.backends.portal_nacional.backend._obter_certificado")
    def test_emitir_rejeitada(self, mock_cert, mock_assinar, mock_client):
        """Rejeição do Portal deve retornar erro com mensagem."""
        mock_cert.return_value = b"cert_bytes"

        from lxml import etree

        mock_assinar.return_value = etree.fromstring("<DPS/>")

        mock_api = MagicMock()
        mock_api.enviar_dps.return_value = RespostaAPI(
            sucesso=False,
            status_code=422,
            mensagem="Campo CNPJ do tomador inválido",
        )
        mock_client.return_value = mock_api

        nota = NotaFiscalServicoFactory()
        resultado = self.backend.emitir(nota, nota.tenant)

        assert resultado.sucesso is False
        assert "CNPJ" in resultado.mensagem

    @patch("caixa_nfse.nfse.backends.portal_nacional.backend._obter_certificado")
    def test_emitir_erro_assinatura(self, mock_cert):
        """Erro na assinatura deve retornar erro."""
        mock_cert.return_value = b"cert_invalido"

        nota = NotaFiscalServicoFactory()
        resultado = self.backend.emitir(nota, nota.tenant)

        # Vai falhar na assinatura XML — capturado pelo except
        assert resultado.sucesso is False

    @patch("caixa_nfse.nfse.backends.portal_nacional.backend._criar_client")
    @patch("caixa_nfse.nfse.backends.portal_nacional.backend.assinar_xml")
    @patch("caixa_nfse.nfse.backends.portal_nacional.backend._obter_certificado")
    def test_emitir_erro_inesperado(self, mock_cert, mock_assinar, mock_client):
        """Exceção inesperada deve ser capturada."""
        mock_cert.return_value = b"cert_bytes"

        from lxml import etree

        mock_assinar.return_value = etree.fromstring("<DPS/>")
        mock_client.side_effect = RuntimeError("erro inesperado")

        nota = NotaFiscalServicoFactory()
        resultado = self.backend.emitir(nota, nota.tenant)

        assert resultado.sucesso is False
        assert "inesperado" in resultado.mensagem.lower()


@pytest.mark.django_db
class TestPortalNacionalBackendConsultar:
    def setup_method(self):
        self.backend = PortalNacionalBackend()

    @patch("caixa_nfse.nfse.backends.portal_nacional.backend._criar_client")
    def test_consultar_por_chave_sucesso(self, mock_client):
        """Consulta por chave de acesso deve retornar status."""
        mock_api = MagicMock()
        mock_api.consultar_por_chave.return_value = RespostaAPI(
            sucesso=True,
            status_code=200,
            dados={"sit": "AUTORIZADA"},
        )
        mock_client.return_value = mock_api

        nota = NotaFiscalServicoFactory(chave_acesso="CHAVE" + "0" * 45)
        resultado = self.backend.consultar(nota, nota.tenant)

        assert resultado.sucesso is True
        assert resultado.status == "AUTORIZADA"

    @patch("caixa_nfse.nfse.backends.portal_nacional.backend._criar_client")
    def test_consultar_por_id_dps(self, mock_client):
        """Sem chave, deve consultar por ID da DPS."""
        mock_api = MagicMock()
        mock_api.consultar_por_dps.return_value = RespostaAPI(
            sucesso=True,
            status_code=200,
            dados={"sit": "PROCESSANDO"},
        )
        mock_client.return_value = mock_api

        nota = NotaFiscalServicoFactory(chave_acesso="", id_dps="DPS999")
        resultado = self.backend.consultar(nota, nota.tenant)

        assert resultado.sucesso is True
        mock_api.consultar_por_dps.assert_called_once_with("DPS999")

    def test_consultar_sem_identificador(self):
        """Sem chave nem ID DPS, deve retornar erro."""
        nota = NotaFiscalServicoFactory(chave_acesso="", id_dps="")
        resultado = self.backend.consultar(nota, nota.tenant)

        assert resultado.sucesso is False
        assert "chave" in resultado.mensagem.lower()

    @patch("caixa_nfse.nfse.backends.portal_nacional.backend._criar_client")
    def test_consultar_erro_api(self, mock_client):
        """Erro na API deve retornar sucesso=False."""
        mock_api = MagicMock()
        mock_api.consultar_por_chave.return_value = RespostaAPI(
            sucesso=False,
            status_code=500,
            mensagem="Erro interno do servidor",
        )
        mock_client.return_value = mock_api

        nota = NotaFiscalServicoFactory(chave_acesso="CHAVE123")
        resultado = self.backend.consultar(nota, nota.tenant)

        assert resultado.sucesso is False

    @patch("caixa_nfse.nfse.backends.portal_nacional.backend._criar_client")
    def test_consultar_excecao(self, mock_client):
        """Exceção deve ser capturada."""
        mock_client.side_effect = Exception("falha")

        nota = NotaFiscalServicoFactory(chave_acesso="CHAVE123")
        resultado = self.backend.consultar(nota, nota.tenant)

        assert resultado.sucesso is False


@pytest.mark.django_db
class TestPortalNacionalBackendCancelar:
    def setup_method(self):
        self.backend = PortalNacionalBackend()

    def test_cancelar_sem_chave(self):
        """Sem chave de acesso, deve retornar erro."""
        nota = NotaFiscalServicoFactory(chave_acesso="")
        resultado = self.backend.cancelar(nota, nota.tenant, "motivo")

        assert resultado.sucesso is False
        assert "chave" in resultado.mensagem.lower()

    @patch("caixa_nfse.nfse.backends.portal_nacional.backend._criar_client")
    def test_cancelar_sucesso(self, mock_client):
        """Cancelamento bem-sucedido."""
        mock_api = MagicMock()
        mock_api.cancelar.return_value = RespostaAPI(
            sucesso=True,
            status_code=200,
            dados={"nProt": "CANCEL789"},
        )
        mock_client.return_value = mock_api

        nota = NotaFiscalServicoFactory(chave_acesso="CHAVE123")
        resultado = self.backend.cancelar(nota, nota.tenant, "Erro de preenchimento")

        assert resultado.sucesso is True
        assert resultado.protocolo == "CANCEL789"

    @patch("caixa_nfse.nfse.backends.portal_nacional.backend._criar_client")
    def test_cancelar_rejeitado(self, mock_client):
        """Cancelamento rejeitado pelo Portal."""
        mock_api = MagicMock()
        mock_api.cancelar.return_value = RespostaAPI(
            sucesso=False,
            status_code=422,
            mensagem="Prazo de cancelamento expirado",
        )
        mock_client.return_value = mock_api

        nota = NotaFiscalServicoFactory(chave_acesso="CHAVE123")
        resultado = self.backend.cancelar(nota, nota.tenant, "motivo")

        assert resultado.sucesso is False
        assert "prazo" in resultado.mensagem.lower()

    @patch("caixa_nfse.nfse.backends.portal_nacional.backend._criar_client")
    def test_cancelar_excecao(self, mock_client):
        """Exceção deve ser capturada."""
        mock_client.side_effect = Exception("falha")

        nota = NotaFiscalServicoFactory(chave_acesso="CHAVE123")
        resultado = self.backend.cancelar(nota, nota.tenant, "motivo")

        assert resultado.sucesso is False


@pytest.mark.django_db
class TestPortalNacionalBackendDanfse:
    def setup_method(self):
        self.backend = PortalNacionalBackend()

    def test_baixar_danfse_sem_chave(self):
        """Sem chave de acesso, retorna None."""
        nota = NotaFiscalServicoFactory(chave_acesso="")
        resultado = self.backend.baixar_danfse(nota, nota.tenant)
        assert resultado is None

    @patch("caixa_nfse.nfse.backends.portal_nacional.backend._criar_client")
    @patch("caixa_nfse.nfse.backends.portal_nacional.backend.baixar_danfse_portal")
    def test_baixar_danfse_sucesso(self, mock_baixar, mock_client):
        """Com chave, deve delegar ao baixar_danfse_portal."""
        mock_baixar.return_value = b"%PDF conteudo"

        nota = NotaFiscalServicoFactory(chave_acesso="CHAVE123")
        resultado = self.backend.baixar_danfse(nota, nota.tenant)

        assert resultado == b"%PDF conteudo"


class TestDanfseService:
    def test_baixar_portal_chave_vazia(self):
        """Chave vazia deve retornar None."""
        client = MagicMock()
        resultado = baixar_danfse_portal(client, "")
        assert resultado is None

    def test_baixar_portal_delega_ao_client(self):
        """Deve chamar client.baixar_danfse com a chave."""
        client = MagicMock()
        client.baixar_danfse.return_value = b"pdf_bytes"
        resultado = baixar_danfse_portal(client, "CHAVE123")
        assert resultado == b"pdf_bytes"
        client.baixar_danfse.assert_called_once_with("CHAVE123")

    def test_baixar_por_url_vazia(self):
        """URL vazia deve retornar None."""
        resultado = baixar_danfse_por_url("")
        assert resultado is None

    @patch("caixa_nfse.nfse.backends.portal_nacional.danfse.httpx.Client")
    def test_baixar_por_url_sucesso(self, mock_client_cls):
        """URL válida com resposta 200 deve retornar bytes."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"%PDF content"

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        resultado = baixar_danfse_por_url("https://example.com/danfse.pdf")
        assert resultado == b"%PDF content"

    @patch("caixa_nfse.nfse.backends.portal_nacional.danfse.httpx.Client")
    def test_baixar_por_url_erro_http(self, mock_client_cls):
        """Resposta não-200 deve retornar None."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        resultado = baixar_danfse_por_url("https://example.com/danfse.pdf")
        assert resultado is None

    @patch("caixa_nfse.nfse.backends.portal_nacional.danfse.httpx.Client")
    def test_baixar_por_url_excecao(self, mock_client_cls):
        """Exceção no download deve retornar None."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.side_effect = Exception("falha")
        mock_client_cls.return_value = mock_client

        resultado = baixar_danfse_por_url("https://example.com/danfse.pdf")
        assert resultado is None


class TestObterCertificado:
    def test_sem_atributo_certificado(self):
        """Tenant sem atributo certificado_digital deve retornar None."""
        tenant = MagicMock(spec=[])  # sem certificado_digital
        assert _obter_certificado(tenant) is None

    def test_certificado_vazio(self):
        """Certificado vazio/falsy deve retornar None."""
        tenant = MagicMock()
        tenant.certificado_digital = None
        assert _obter_certificado(tenant) is None

    def test_certificado_leitura_sucesso(self):
        """Deve retornar bytes quando leitura é bem-sucedida."""
        tenant = MagicMock()
        tenant.certificado_digital = MagicMock()
        tenant.certificado_digital.read.return_value = b"cert_bytes"
        assert _obter_certificado(tenant) == b"cert_bytes"

    def test_certificado_leitura_erro(self):
        """Erro na leitura deve retornar None sem propagar exceção."""
        tenant = MagicMock()
        tenant.certificado_digital = MagicMock()
        tenant.certificado_digital.read.side_effect = OSError("falha I/O")
        assert _obter_certificado(tenant) is None
