"""
Mock backend for NFS-e — used in testing and development.
Simulates authorization without calling any external API.
"""

import uuid

from caixa_nfse.nfse.backends.base import (
    BaseNFSeBackend,
    ResultadoCancelamento,
    ResultadoConsulta,
    ResultadoEmissao,
)


class MockBackend(BaseNFSeBackend):
    """Simulates NFS-e operations for testing and development."""

    def emitir(self, nota, tenant) -> ResultadoEmissao:
        return ResultadoEmissao(
            sucesso=True,
            numero_nfse=str(nota.numero_rps),
            chave_acesso=f"MOCK{(uuid.uuid4().hex + uuid.uuid4().hex)[:46].upper()}",
            codigo_verificacao=f"MOCK-{uuid.uuid4().hex[:8].upper()}",
            protocolo=f"MOCK-{uuid.uuid4().hex[:12].upper()}",
            xml_retorno="<nfse><mock>true</mock></nfse>",
            pdf_url="",
            mensagem="NFS-e emitida com sucesso (mock)",
        )

    def consultar(self, nota, tenant) -> ResultadoConsulta:
        return ResultadoConsulta(
            sucesso=True,
            status=nota.status,
            xml_retorno="<consulta><mock>true</mock></consulta>",
            mensagem="Consulta realizada com sucesso (mock)",
        )

    def cancelar(self, nota, tenant, motivo: str) -> ResultadoCancelamento:
        return ResultadoCancelamento(
            sucesso=True,
            protocolo=f"CANCEL-{uuid.uuid4().hex[:12].upper()}",
            mensagem=f"Cancelamento realizado com sucesso (mock): {motivo}",
        )

    def baixar_danfse(self, nota, tenant) -> bytes | None:
        return None
