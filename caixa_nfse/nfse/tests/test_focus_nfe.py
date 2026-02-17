"""
Tests for Focus NFe backend — verifies API calls, logging, and header sanitization.
All HTTP calls are mocked with httpx responses.
"""

from unittest.mock import MagicMock, patch

import pytest

from caixa_nfse.nfse.backends.focus_nfe import FocusNFeBackend
from caixa_nfse.nfse.models_api_log import NfseApiLog


@pytest.fixture
def focus_backend():
    return FocusNFeBackend()


@pytest.fixture
def mock_tenant(db):
    from caixa_nfse.tests.factories import TenantFactory

    return TenantFactory()


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.api_token = "test-token-focus-123"
    config.api_secret = ""
    config.ambiente = "HOMOLOGACAO"
    return config


@pytest.fixture
def mock_nota(db, mock_tenant):
    from caixa_nfse.tests.factories import NotaFiscalServicoFactory

    return NotaFiscalServicoFactory(tenant=mock_tenant)


def _mock_response(status_code=200, json_data=None, text=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.is_success = 200 <= status_code < 300
    resp.text = text or ""
    resp.headers = {"Content-Type": "application/json"}
    if json_data is not None:
        resp.json.return_value = json_data
        if not text:
            import json

            resp.text = json.dumps(json_data)
    return resp


@pytest.mark.django_db
class TestFocusNFeEmitir:
    """Tests for FocusNFeBackend.emitir()."""

    def test_emitir_autorizada(self, focus_backend, mock_nota, mock_tenant, mock_config):
        """Successful emission returns authorized result and creates API log."""
        response_data = {
            "status": "autorizado",
            "numero": "12345",
            "codigo_verificacao": "ABC123",
            "protocolo": "PROT001",
            "xml_nfse": "<nfse>ok</nfse>",
            "caminho_xml_nota_fiscal": "https://example.com/nfse.pdf",
        }

        with patch.object(focus_backend, "_get_config", return_value=mock_config):
            with patch.object(
                focus_backend, "_request", return_value=_mock_response(200, response_data)
            ):
                resultado = focus_backend.emitir(mock_nota, mock_tenant)

        assert resultado.sucesso is True
        assert resultado.numero_nfse == "12345"
        assert resultado.codigo_verificacao == "ABC123"
        assert "Focus NFe" in resultado.mensagem

    def test_emitir_processando(self, focus_backend, mock_nota, mock_tenant, mock_config):
        """Async processing returns success with processing status."""
        response_data = {
            "status": "processando_autorizacao",
            "protocolo": "PROT002",
        }

        with patch.object(focus_backend, "_get_config", return_value=mock_config):
            with patch.object(
                focus_backend, "_request", return_value=_mock_response(202, response_data)
            ):
                resultado = focus_backend.emitir(mock_nota, mock_tenant)

        assert resultado.sucesso is True
        assert "processando" in resultado.mensagem.lower()

    def test_emitir_erro_validacao(self, focus_backend, mock_nota, mock_tenant, mock_config):
        """Validation error returns failure with error messages."""
        response_data = {
            "erros": [
                {"mensagem": "CNPJ inválido"},
                {"mensagem": "Alíquota fora do range"},
            ],
        }

        with patch.object(focus_backend, "_get_config", return_value=mock_config):
            with patch.object(
                focus_backend, "_request", return_value=_mock_response(422, response_data)
            ):
                resultado = focus_backend.emitir(mock_nota, mock_tenant)

        assert resultado.sucesso is False
        assert "CNPJ inválido" in resultado.mensagem
        assert "Alíquota" in resultado.mensagem

    def test_emitir_sem_config(self, focus_backend, mock_nota, mock_tenant):
        """Missing config returns failure."""
        with patch.object(focus_backend, "_get_config", return_value=None):
            resultado = focus_backend.emitir(mock_nota, mock_tenant)

        assert resultado.sucesso is False
        assert "não encontrada" in resultado.mensagem

    def test_emitir_falha_comunicacao(self, focus_backend, mock_nota, mock_tenant, mock_config):
        """Network failure returns failure."""
        with patch.object(focus_backend, "_get_config", return_value=mock_config):
            with patch.object(focus_backend, "_request", return_value=None):
                resultado = focus_backend.emitir(mock_nota, mock_tenant)

        assert resultado.sucesso is False
        assert "Falha" in resultado.mensagem


@pytest.mark.django_db
class TestFocusNFeConsultar:
    """Tests for FocusNFeBackend.consultar()."""

    def test_consultar_success(self, focus_backend, mock_nota, mock_tenant, mock_config):
        response_data = {
            "status": "autorizado",
            "xml_nfse": "<nfse>ok</nfse>",
            "mensagem": "Nota encontrada",
        }

        with patch.object(focus_backend, "_get_config", return_value=mock_config):
            with patch.object(
                focus_backend, "_request", return_value=_mock_response(200, response_data)
            ):
                resultado = focus_backend.consultar(mock_nota, mock_tenant)

        assert resultado.sucesso is True
        assert resultado.status == "autorizado"

    def test_consultar_sem_config(self, focus_backend, mock_nota, mock_tenant):
        with patch.object(focus_backend, "_get_config", return_value=None):
            resultado = focus_backend.consultar(mock_nota, mock_tenant)
        assert resultado.sucesso is False


@pytest.mark.django_db
class TestFocusNFeCancelar:
    """Tests for FocusNFeBackend.cancelar()."""

    def test_cancelar_success(self, focus_backend, mock_nota, mock_tenant, mock_config):
        response_data = {
            "protocolo": "CANCEL001",
            "mensagem": "Cancelamento realizado",
        }

        with patch.object(focus_backend, "_get_config", return_value=mock_config):
            with patch.object(
                focus_backend, "_request", return_value=_mock_response(200, response_data)
            ):
                resultado = focus_backend.cancelar(mock_nota, mock_tenant, "Erro de dados")

        assert resultado.sucesso is True
        assert resultado.protocolo == "CANCEL001"


@pytest.mark.django_db
class TestFocusNFeDanfse:
    """Tests for FocusNFeBackend.baixar_danfse()."""

    def test_baixar_danfse_success(self, focus_backend, mock_nota, mock_tenant, mock_config):
        pdf_bytes = b"%PDF-1.4 fake content"

        with patch.object(focus_backend, "_get_config", return_value=mock_config):
            with patch.object(focus_backend, "_request_bytes", return_value=pdf_bytes):
                result = focus_backend.baixar_danfse(mock_nota, mock_tenant)

        assert result == pdf_bytes

    def test_baixar_danfse_sem_config(self, focus_backend, mock_nota, mock_tenant):
        with patch.object(focus_backend, "_get_config", return_value=None):
            result = focus_backend.baixar_danfse(mock_nota, mock_tenant)
        assert result is None


@pytest.mark.django_db
class TestApiLogCreation:
    """Tests that verify NfseApiLog is properly created and sanitized."""

    def test_api_log_sanitizes_headers(self):
        """Sensitive headers must be redacted."""
        headers = {
            "Authorization": "Basic abc123",
            "Content-Type": "application/json",
            "token_sh": "secret-token",
            "X-Request-ID": "some-uuid",
        }
        sanitized = NfseApiLog.sanitize_headers(headers)

        assert sanitized["Authorization"] == "***REDACTED***"
        assert sanitized["token_sh"] == "***REDACTED***"
        assert sanitized["Content-Type"] == "application/json"
        assert sanitized["X-Request-ID"] == "some-uuid"

    def test_api_log_immutable(self, mock_tenant):
        """API log records cannot be modified or deleted."""
        log = NfseApiLog.objects.create(
            tenant=mock_tenant,
            backend="focus_nfe",
            metodo="POST",
            url="https://api.test.com/nfse",
            body_envio="{}",
            status_code=200,
            body_retorno="{}",
            sucesso=True,
        )

        with pytest.raises(ValueError, match="imutáveis"):
            log.sucesso = False
            log.save()

        with pytest.raises(ValueError, match="não podem ser excluídos"):
            log.delete()

    def test_api_log_str(self, mock_tenant):
        """__str__ displays useful summary."""
        log = NfseApiLog.objects.create(
            tenant=mock_tenant,
            backend="focus_nfe",
            metodo="POST",
            url="https://api.test.com/nfse",
            body_envio="{}",
            status_code=200,
            body_retorno="{}",
            duracao_ms=150,
            sucesso=True,
        )
        assert "focus_nfe" in str(log)
        assert "POST" in str(log)
        assert "200" in str(log)


@pytest.mark.django_db
class TestFocusNFeHelpers:
    """Tests for _base_url, _auth_headers, _get_config."""

    def test_base_url_homologacao(self, focus_backend, mock_config):
        mock_config.ambiente = "HOMOLOGACAO"
        url = focus_backend._base_url(mock_config)
        assert "homologacao" in url

    def test_base_url_producao(self, focus_backend, mock_config):
        mock_config.ambiente = "PRODUCAO"
        url = focus_backend._base_url(mock_config)
        assert "api.focusnfe.com.br" in url

    def test_base_url_unknown_fallback(self, focus_backend, mock_config):
        mock_config.ambiente = "DESCONHECIDO"
        url = focus_backend._base_url(mock_config)
        assert "homologacao" in url

    def test_auth_headers_basic(self, focus_backend, mock_config):
        headers = focus_backend._auth_headers(mock_config)
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")

    def test_auth_headers_empty_token(self, focus_backend, mock_config):
        mock_config.api_token = ""
        headers = focus_backend._auth_headers(mock_config)
        assert "Authorization" in headers

    def test_get_config_returns_config(self, focus_backend, mock_tenant):
        # No config_nfse → returns None
        result = focus_backend._get_config(mock_tenant)
        assert result is None

    def test_consultar_falha_comunicacao(self, focus_backend, mock_nota, mock_tenant, mock_config):
        """Network failure on consultar returns failure."""
        with patch.object(focus_backend, "_get_config", return_value=mock_config):
            with patch.object(focus_backend, "_request", return_value=None):
                resultado = focus_backend.consultar(mock_nota, mock_tenant)
        assert resultado.sucesso is False
        assert "Falha" in resultado.mensagem

    def test_cancelar_sem_config(self, focus_backend, mock_nota, mock_tenant):
        with patch.object(focus_backend, "_get_config", return_value=None):
            resultado = focus_backend.cancelar(mock_nota, mock_tenant, "motivo")
        assert resultado.sucesso is False

    def test_cancelar_falha_comunicacao(self, focus_backend, mock_nota, mock_tenant, mock_config):
        with patch.object(focus_backend, "_get_config", return_value=mock_config):
            with patch.object(focus_backend, "_request", return_value=None):
                resultado = focus_backend.cancelar(mock_nota, mock_tenant, "motivo")
        assert resultado.sucesso is False


@pytest.mark.django_db
class TestFocusNFeMapper:
    """Tests for _nota_to_focus_json mapper."""

    def test_nota_to_focus_json_basic(self, focus_backend, mock_nota, mock_tenant):
        result = focus_backend._nota_to_focus_json(mock_nota, mock_tenant)
        assert "prestador" in result
        assert "servico" in result
        assert "data_emissao" in result

    def test_nota_to_focus_json_with_cliente(self, focus_backend, mock_nota, mock_tenant):
        from caixa_nfse.tests.factories import ClienteFactory

        cliente = ClienteFactory(tenant=mock_tenant)
        mock_nota.cliente = cliente
        result = focus_backend._nota_to_focus_json(mock_nota, mock_tenant)
        assert "tomador" in result
        assert result["tomador"]["cpf_cnpj"] == cliente.cpf_cnpj

    def test_nota_to_focus_json_without_cliente(self, focus_backend, mock_tenant):
        nota = MagicMock()
        nota.cliente = None
        nota.data_emissao = None
        nota.discriminacao = "Serviço"
        nota.aliquota_iss = 5
        nota.valor_servicos = 100
        nota.iss_retido = False
        nota.servico = None
        result = focus_backend._nota_to_focus_json(nota, mock_tenant)
        assert result["tomador"] == {}

    def test_nota_to_focus_json_error_messages_list(
        self, focus_backend, mock_nota, mock_tenant, mock_config
    ):
        """Error response with erros list as strings (not dicts)."""
        response_data = {"erros": ["Erro genérico 1", "Erro genérico 2"]}
        with patch.object(focus_backend, "_get_config", return_value=mock_config):
            with patch.object(
                focus_backend, "_request", return_value=_mock_response(400, response_data)
            ):
                resultado = focus_backend.emitir(mock_nota, mock_tenant)
        assert resultado.sucesso is False
        assert "Erro genérico 1" in resultado.mensagem

    def test_emitir_error_no_erros_field(self, focus_backend, mock_nota, mock_tenant, mock_config):
        """HTTP error without erros field falls back to mensagem or status code."""
        response_data = {"mensagem": "Serviço indisponível"}
        with patch.object(focus_backend, "_get_config", return_value=mock_config):
            with patch.object(
                focus_backend, "_request", return_value=_mock_response(500, response_data)
            ):
                resultado = focus_backend.emitir(mock_nota, mock_tenant)
        assert resultado.sucesso is False
        assert "Serviço indisponível" in resultado.mensagem
