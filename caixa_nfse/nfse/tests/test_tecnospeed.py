"""
Tests for TecnoSpeed backend — verifies API calls, logging, and header sanitization.
All HTTP calls are mocked with httpx responses.
"""

from unittest.mock import MagicMock, patch

import pytest

from caixa_nfse.nfse.backends.tecnospeed import TecnoSpeedBackend
from caixa_nfse.nfse.models_api_log import NfseApiLog


@pytest.fixture
def ts_backend():
    return TecnoSpeedBackend()


@pytest.fixture
def mock_tenant(db):
    from caixa_nfse.tests.factories import TenantFactory

    return TenantFactory()


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.api_token = "test-token-tecnospeed-456"
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
class TestTecnoSpeedEmitir:
    """Tests for TecnoSpeedBackend.emitir()."""

    def test_emitir_autorizada(self, ts_backend, mock_nota, mock_tenant, mock_config):
        """Successful emission returns authorized result."""
        response_data = {
            "situacao": "autorizada",
            "numero_nfse": "99887",
            "codigo_verificacao": "XYZ789",
            "protocolo": "TS-PROT001",
            "xml": "<nfse>autorizada</nfse>",
            "link_pdf": "https://ts.com/nfse.pdf",
        }

        with patch.object(ts_backend, "_get_config", return_value=mock_config):
            with patch.object(
                ts_backend, "_request", return_value=_mock_response(200, response_data)
            ):
                resultado = ts_backend.emitir(mock_nota, mock_tenant)

        assert resultado.sucesso is True
        assert resultado.numero_nfse == "99887"
        assert resultado.codigo_verificacao == "XYZ789"
        assert "TecnoSpeed" in resultado.mensagem

    def test_emitir_processando(self, ts_backend, mock_nota, mock_tenant, mock_config):
        """Async processing returns success with processing status."""
        response_data = {
            "situacao": "processando",
            "protocolo": "TS-PROT002",
        }

        with patch.object(ts_backend, "_get_config", return_value=mock_config):
            with patch.object(
                ts_backend, "_request", return_value=_mock_response(202, response_data)
            ):
                resultado = ts_backend.emitir(mock_nota, mock_tenant)

        assert resultado.sucesso is True
        assert "processando" in resultado.mensagem.lower()

    def test_emitir_erro_validacao(self, ts_backend, mock_nota, mock_tenant, mock_config):
        """Validation error returns failure with error messages."""
        response_data = {
            "erros": [
                {"mensagem": "Inscrição municipal obrigatória"},
            ],
        }

        with patch.object(ts_backend, "_get_config", return_value=mock_config):
            with patch.object(
                ts_backend, "_request", return_value=_mock_response(400, response_data)
            ):
                resultado = ts_backend.emitir(mock_nota, mock_tenant)

        assert resultado.sucesso is False
        assert "Inscrição municipal" in resultado.mensagem

    def test_emitir_erro_string(self, ts_backend, mock_nota, mock_tenant, mock_config):
        """Error as plain string is handled."""
        response_data = {
            "erros": "Erro interno do servidor",
        }

        with patch.object(ts_backend, "_get_config", return_value=mock_config):
            with patch.object(
                ts_backend, "_request", return_value=_mock_response(500, response_data)
            ):
                resultado = ts_backend.emitir(mock_nota, mock_tenant)

        assert resultado.sucesso is False
        assert "Erro interno" in resultado.mensagem

    def test_emitir_sem_config(self, ts_backend, mock_nota, mock_tenant):
        """Missing config returns failure."""
        with patch.object(ts_backend, "_get_config", return_value=None):
            resultado = ts_backend.emitir(mock_nota, mock_tenant)
        assert resultado.sucesso is False

    def test_emitir_falha_comunicacao(self, ts_backend, mock_nota, mock_tenant, mock_config):
        """Network failure returns failure."""
        with patch.object(ts_backend, "_get_config", return_value=mock_config):
            with patch.object(ts_backend, "_request", return_value=None):
                resultado = ts_backend.emitir(mock_nota, mock_tenant)
        assert resultado.sucesso is False


@pytest.mark.django_db
class TestTecnoSpeedConsultar:
    """Tests for TecnoSpeedBackend.consultar()."""

    def test_consultar_success(self, ts_backend, mock_nota, mock_tenant, mock_config):
        response_data = {
            "situacao": "autorizada",
            "xml": "<nfse>ok</nfse>",
            "mensagem": "Nota encontrada",
        }

        with patch.object(ts_backend, "_get_config", return_value=mock_config):
            with patch.object(
                ts_backend, "_request", return_value=_mock_response(200, response_data)
            ):
                resultado = ts_backend.consultar(mock_nota, mock_tenant)

        assert resultado.sucesso is True
        assert resultado.status == "autorizada"

    def test_consultar_sem_config(self, ts_backend, mock_nota, mock_tenant):
        with patch.object(ts_backend, "_get_config", return_value=None):
            resultado = ts_backend.consultar(mock_nota, mock_tenant)
        assert resultado.sucesso is False


@pytest.mark.django_db
class TestTecnoSpeedCancelar:
    """Tests for TecnoSpeedBackend.cancelar()."""

    def test_cancelar_success(self, ts_backend, mock_nota, mock_tenant, mock_config):
        response_data = {
            "protocolo": "TS-CANCEL001",
            "mensagem": "Cancelamento realizado",
        }

        with patch.object(ts_backend, "_get_config", return_value=mock_config):
            with patch.object(
                ts_backend, "_request", return_value=_mock_response(200, response_data)
            ):
                resultado = ts_backend.cancelar(mock_nota, mock_tenant, "Erro de cálculo")

        assert resultado.sucesso is True
        assert resultado.protocolo == "TS-CANCEL001"

    def test_cancelar_sem_config(self, ts_backend, mock_nota, mock_tenant):
        with patch.object(ts_backend, "_get_config", return_value=None):
            resultado = ts_backend.cancelar(mock_nota, mock_tenant, "Motivo")
        assert resultado.sucesso is False


@pytest.mark.django_db
class TestTecnoSpeedDanfse:
    """Tests for TecnoSpeedBackend.baixar_danfse()."""

    def test_baixar_danfse_success(self, ts_backend, mock_nota, mock_tenant, mock_config):
        pdf_bytes = b"%PDF-1.5 ts content"

        with patch.object(ts_backend, "_get_config", return_value=mock_config):
            with patch.object(ts_backend, "_request_bytes", return_value=pdf_bytes):
                result = ts_backend.baixar_danfse(mock_nota, mock_tenant)

        assert result == pdf_bytes

    def test_baixar_danfse_sem_config(self, ts_backend, mock_nota, mock_tenant):
        with patch.object(ts_backend, "_get_config", return_value=None):
            result = ts_backend.baixar_danfse(mock_nota, mock_tenant)
        assert result is None


@pytest.mark.django_db
class TestTecnoSpeedAuthHeaders:
    """Tests for TecnoSpeed-specific auth header."""

    def test_auth_header_uses_token_sh(self, ts_backend, mock_config):
        headers = ts_backend._auth_headers(mock_config)
        assert headers["token_sh"] == "test-token-tecnospeed-456"

    def test_token_sh_sanitized_in_log(self):
        headers = {"token_sh": "secret", "Content-Type": "application/json"}
        sanitized = NfseApiLog.sanitize_headers(headers)
        assert sanitized["token_sh"] == "***REDACTED***"
        assert sanitized["Content-Type"] == "application/json"
