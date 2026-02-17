"""
Tests for GatewayHttpClient (_request and _request_bytes).
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from caixa_nfse.nfse.backends.gateway_http import GatewayHttpClient
from caixa_nfse.tests.factories import TenantFactory


class ConcreteGateway(GatewayHttpClient):
    """Concrete implementation for testing."""

    backend_name = "test_gateway"

    def _base_url(self, config) -> str:
        return "https://api.example.com"

    def _auth_headers(self, config) -> dict:
        return {"Authorization": "Bearer test-token"}


@pytest.fixture
def gateway():
    return ConcreteGateway()


@pytest.fixture
def mock_config():
    return MagicMock()


def _make_response(status_code=200, text="{}", content=b"", is_success=True):
    """Create a proper mock response with real values (not MagicMock)."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.headers = {"Content-Type": "application/json"}
    resp.text = text
    resp.content = content
    resp.is_success = is_success
    return resp


@pytest.mark.django_db
class TestGatewayHttpClientRequest:
    """Tests for _request method."""

    @patch("caixa_nfse.nfse.backends.gateway_http.NfseApiLog")
    @patch("caixa_nfse.nfse.backends.gateway_http.httpx.Client")
    def test_successful_json_request(self, mock_client_cls, mock_log, gateway, mock_config):
        tenant = TenantFactory()
        mock_response = _make_response(200, '{"status": "ok"}')

        ctx = MagicMock()
        ctx.request.return_value = mock_response
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=ctx)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = gateway._request(
            "POST",
            "/test",
            config=mock_config,
            tenant=tenant,
            json_body={"key": "value"},
        )

        assert result is not None
        assert result.status_code == 200
        mock_log.objects.create.assert_called_once()

    @patch("caixa_nfse.nfse.backends.gateway_http.NfseApiLog")
    @patch("caixa_nfse.nfse.backends.gateway_http.httpx.Client")
    def test_timeout_returns_none(self, mock_client_cls, mock_log, gateway, mock_config):
        tenant = TenantFactory()

        ctx = MagicMock()
        ctx.request.side_effect = httpx.TimeoutException("timeout")
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=ctx)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = gateway._request("GET", "/slow", config=mock_config, tenant=tenant)

        assert result is None
        mock_log.objects.create.assert_called_once()

    @patch("caixa_nfse.nfse.backends.gateway_http.NfseApiLog")
    @patch("caixa_nfse.nfse.backends.gateway_http.httpx.Client")
    def test_http_error_returns_none(self, mock_client_cls, mock_log, gateway, mock_config):
        tenant = TenantFactory()

        ctx = MagicMock()
        ctx.request.side_effect = httpx.HTTPError("connection failed")
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=ctx)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = gateway._request("GET", "/error", config=mock_config, tenant=tenant)

        assert result is None
        mock_log.objects.create.assert_called_once()

    @patch("caixa_nfse.nfse.backends.gateway_http.NfseApiLog")
    @patch("caixa_nfse.nfse.backends.gateway_http.httpx.Client")
    def test_request_with_params(self, mock_client_cls, mock_log, gateway, mock_config):
        tenant = TenantFactory()
        mock_response = _make_response()

        ctx = MagicMock()
        ctx.request.return_value = mock_response
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=ctx)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = gateway._request(
            "GET",
            "/search",
            config=mock_config,
            tenant=tenant,
            params={"q": "test"},
        )

        assert result is not None


@pytest.mark.django_db
class TestGatewayHttpClientRequestBytes:
    """Tests for _request_bytes method."""

    @patch("caixa_nfse.nfse.backends.gateway_http.NfseApiLog")
    @patch("caixa_nfse.nfse.backends.gateway_http.httpx.Client")
    def test_successful_binary_download(self, mock_client_cls, mock_log, gateway, mock_config):
        tenant = TenantFactory()
        mock_response = _make_response(200, content=b"%PDF-1.4 fake", is_success=True)

        ctx = MagicMock()
        ctx.request.return_value = mock_response
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=ctx)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = gateway._request_bytes("GET", "/doc.pdf", config=mock_config, tenant=tenant)

        assert result == b"%PDF-1.4 fake"

    @patch("caixa_nfse.nfse.backends.gateway_http.NfseApiLog")
    @patch("caixa_nfse.nfse.backends.gateway_http.httpx.Client")
    def test_binary_download_failure(self, mock_client_cls, mock_log, gateway, mock_config):
        tenant = TenantFactory()
        mock_response = _make_response(404, content=b"", is_success=False)

        ctx = MagicMock()
        ctx.request.return_value = mock_response
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=ctx)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = gateway._request_bytes("GET", "/missing.pdf", config=mock_config, tenant=tenant)

        assert result is None

    @patch("caixa_nfse.nfse.backends.gateway_http.NfseApiLog")
    @patch("caixa_nfse.nfse.backends.gateway_http.httpx.Client")
    def test_binary_download_http_error(self, mock_client_cls, mock_log, gateway, mock_config):
        tenant = TenantFactory()

        ctx = MagicMock()
        ctx.request.side_effect = httpx.HTTPError("network error")
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=ctx)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = gateway._request_bytes("GET", "/broken.pdf", config=mock_config, tenant=tenant)

        assert result is None
        mock_log.objects.create.assert_called_once()
