"""
API Serializers.
"""

from rest_framework import serializers

from caixa_nfse.caixa.models import Caixa
from caixa_nfse.clientes.models import Cliente
from caixa_nfse.nfse.models import NotaFiscalServico


class CaixaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Caixa
        fields = [
            "id",
            "identificador",
            "tipo",
            "status",
            "saldo_atual",
            "ativo",
            "created_at",
        ]
        read_only_fields = ["id", "saldo_atual", "created_at"]


class ClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        fields = [
            "id",
            "tipo_pessoa",
            "cpf_cnpj",
            "razao_social",
            "nome_fantasia",
            "email",
            "telefone",
            "cidade",
            "uf",
            "ativo",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class NotaFiscalSerializer(serializers.ModelSerializer):
    cliente_nome = serializers.CharField(source="cliente.razao_social", read_only=True)

    class Meta:
        model = NotaFiscalServico
        fields = [
            "id",
            "numero_rps",
            "numero_nfse",
            "status",
            "cliente",
            "cliente_nome",
            "data_emissao",
            "competencia",
            "valor_servicos",
            "valor_iss",
            "valor_liquido",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "numero_nfse",
            "status",
            "valor_iss",
            "valor_liquido",
            "created_at",
        ]
