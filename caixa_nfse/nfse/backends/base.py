"""
Abstract base backend for NFS-e emission.
All concrete backends must implement this interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ResultadoEmissao:
    """Result of an NFS-e emission attempt."""

    sucesso: bool
    numero_nfse: str | None = None
    chave_acesso: str | None = None
    codigo_verificacao: str | None = None
    protocolo: str | None = None
    xml_envio: str | None = None
    xml_retorno: str | None = None
    pdf_url: str | None = None
    json_bruto: dict | None = None
    mensagem: str = ""


@dataclass
class ResultadoConsulta:
    """Result of an NFS-e query."""

    sucesso: bool
    status: str | None = None
    xml_retorno: str | None = None
    mensagem: str = ""


@dataclass
class ResultadoCancelamento:
    """Result of an NFS-e cancellation."""

    sucesso: bool
    protocolo: str | None = None
    mensagem: str = ""


class BaseNFSeBackend(ABC):
    """
    Abstract interface for NFS-e backends.
    Every backend must implement emitir, consultar, cancelar, and baixar_danfse.
    """

    @abstractmethod
    def emitir(self, nota, tenant) -> ResultadoEmissao:
        """Emit an NFS-e for the given invoice."""

    @abstractmethod
    def consultar(self, nota, tenant) -> ResultadoConsulta:
        """Query the status of an NFS-e."""

    @abstractmethod
    def cancelar(self, nota, tenant, motivo: str) -> ResultadoCancelamento:
        """Cancel an authorized NFS-e."""

    @abstractmethod
    def baixar_danfse(self, nota, tenant) -> bytes | None:
        """Download the DANFSe PDF. Returns bytes or None."""
