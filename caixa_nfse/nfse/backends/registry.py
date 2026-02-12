"""
Backend registry — factory for selecting the appropriate NFS-e backend
based on the tenant's ConfiguracaoNFSe.
"""

import logging

from caixa_nfse.nfse.backends.base import BaseNFSeBackend

logger = logging.getLogger(__name__)

_BACKEND_MAP: dict[str, type[BaseNFSeBackend]] = {}


def register_backend(key: str, backend_class: type[BaseNFSeBackend]) -> None:
    """Register a backend class under the given key."""
    _BACKEND_MAP[key] = backend_class


def _ensure_defaults() -> None:
    """Lazily register built-in backends on first access."""
    if "mock" not in _BACKEND_MAP:
        from caixa_nfse.nfse.backends.mock import MockBackend

        register_backend("mock", MockBackend)

    if "portal_nacional" not in _BACKEND_MAP:
        from caixa_nfse.nfse.backends.portal_nacional import PortalNacionalBackend

        register_backend("portal_nacional", PortalNacionalBackend)


def get_backend(tenant) -> BaseNFSeBackend:
    """
    Return the correct backend instance for a tenant.
    Falls back to MockBackend if no config exists or backend is unknown.
    """
    _ensure_defaults()

    config = _get_config(tenant)
    if config is None:
        logger.info("No ConfiguracaoNFSe for tenant %s, falling back to MockBackend", tenant)
        return _BACKEND_MAP["mock"]()

    backend_key = config.backend
    backend_class = _BACKEND_MAP.get(backend_key)

    if backend_class is None:
        logger.warning(
            "Unknown backend '%s' for tenant %s, falling back to MockBackend",
            backend_key,
            tenant,
        )
        return _BACKEND_MAP["mock"]()

    return backend_class()


def _get_config(tenant) -> object | None:
    """Fetch ConfiguracaoNFSe for a tenant, or None."""
    try:
        return tenant.config_nfse
    except Exception:
        return None


def list_backends() -> dict[str, type[BaseNFSeBackend]]:
    """Return a copy of the registered backends map."""
    _ensure_defaults()
    return dict(_BACKEND_MAP)
