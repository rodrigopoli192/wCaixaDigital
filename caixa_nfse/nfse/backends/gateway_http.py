"""
Base HTTP client for NFS-e gateways with automatic API logging.

Every HTTP call is recorded in NfseApiLog with sanitized headers,
timing, and UUID correlation. Concrete backends inherit from
GatewayHttpClient and get logging for free.
"""

import json
import logging
import time
import uuid

import httpx

from caixa_nfse.nfse.models_api_log import NfseApiLog

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30  # seconds


class GatewayHttpClient:
    """
    HTTP client wrapper that logs every request/response to NfseApiLog.

    Subclasses set ``backend_name``, ``base_url``, and override
    ``_auth_headers(config)`` to provide gateway-specific auth.
    """

    backend_name: str = ""
    timeout: int = DEFAULT_TIMEOUT

    def _base_url(self, config) -> str:
        """Return the base URL for the gateway based on environment."""
        raise NotImplementedError

    def _auth_headers(self, config) -> dict:
        """Return auth headers for the gateway. Subclasses must implement."""
        raise NotImplementedError

    def _request(
        self,
        method: str,
        path: str,
        *,
        config,
        tenant,
        nota=None,
        json_body: dict | None = None,
        params: dict | None = None,
    ) -> httpx.Response | None:
        """
        Execute HTTP request and log it to NfseApiLog.

        Returns httpx.Response on success, None on network/timeout error.
        The NfseApiLog record is always created regardless of outcome.
        """
        request_id = uuid.uuid4()
        url = f"{self._base_url(config).rstrip('/')}/{path.lstrip('/')}"

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Request-ID": str(request_id),
        }
        headers.update(self._auth_headers(config))

        body_str = json.dumps(json_body, ensure_ascii=False) if json_body else ""

        log_kwargs = {
            "tenant": tenant,
            "nota": nota,
            "backend": self.backend_name,
            "metodo": method.upper(),
            "url": url,
            "headers_envio": NfseApiLog.sanitize_headers(headers),
            "body_envio": body_str,
            "request_id": request_id,
        }

        start = time.monotonic()
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.request(
                    method,
                    url,
                    headers=headers,
                    json=json_body,
                    params=params,
                )

            elapsed_ms = int((time.monotonic() - start) * 1000)

            NfseApiLog.objects.create(
                **log_kwargs,
                status_code=response.status_code,
                headers_retorno=NfseApiLog.sanitize_headers(dict(response.headers)),
                body_retorno=response.text[:10_000],  # cap at 10KB
                duracao_ms=elapsed_ms,
                sucesso=response.is_success,
            )

            logger.info(
                "[%s] %s %s → %s (%dms) req=%s",
                self.backend_name,
                method.upper(),
                url,
                response.status_code,
                elapsed_ms,
                request_id,
            )
            return response

        except httpx.TimeoutException as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            NfseApiLog.objects.create(
                **log_kwargs,
                duracao_ms=elapsed_ms,
                sucesso=False,
                erro=f"Timeout após {elapsed_ms}ms: {exc}",
            )
            logger.error(
                "[%s] TIMEOUT %s %s (%dms) req=%s",
                self.backend_name,
                method.upper(),
                url,
                elapsed_ms,
                request_id,
            )
            return None

        except httpx.HTTPError as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            NfseApiLog.objects.create(
                **log_kwargs,
                duracao_ms=elapsed_ms,
                sucesso=False,
                erro=f"HTTP error: {exc}",
            )
            logger.error(
                "[%s] ERROR %s %s: %s req=%s",
                self.backend_name,
                method.upper(),
                url,
                exc,
                request_id,
            )
            return None

    def _request_bytes(
        self,
        method: str,
        path: str,
        *,
        config,
        tenant,
        nota=None,
    ) -> bytes | None:
        """Execute request expecting binary content (e.g. PDF download)."""
        request_id = uuid.uuid4()
        url = f"{self._base_url(config).rstrip('/')}/{path.lstrip('/')}"

        headers = {"X-Request-ID": str(request_id)}
        headers.update(self._auth_headers(config))

        start = time.monotonic()
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.request(method, url, headers=headers)

            elapsed_ms = int((time.monotonic() - start) * 1000)

            NfseApiLog.objects.create(
                tenant=tenant,
                nota=nota,
                backend=self.backend_name,
                metodo=method.upper(),
                url=url,
                headers_envio=NfseApiLog.sanitize_headers(headers),
                body_envio="",
                status_code=response.status_code,
                headers_retorno=NfseApiLog.sanitize_headers(dict(response.headers)),
                body_retorno=f"<binary {len(response.content)} bytes>",
                duracao_ms=elapsed_ms,
                sucesso=response.is_success,
                request_id=request_id,
            )

            return response.content if response.is_success else None

        except httpx.HTTPError as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            NfseApiLog.objects.create(
                tenant=tenant,
                nota=nota,
                backend=self.backend_name,
                metodo=method.upper(),
                url=url,
                headers_envio=NfseApiLog.sanitize_headers(headers),
                body_envio="",
                duracao_ms=elapsed_ms,
                sucesso=False,
                erro=str(exc),
                request_id=request_id,
            )
            return None
