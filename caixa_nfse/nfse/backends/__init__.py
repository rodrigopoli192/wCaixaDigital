"""
NFS-e backends - Strategy Pattern for pluggable providers.
"""

from caixa_nfse.nfse.backends.registry import get_backend

__all__ = ["get_backend"]
