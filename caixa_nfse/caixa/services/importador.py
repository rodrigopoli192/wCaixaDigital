"""
Service layer for importing movements from external databases via Rotinas SQL.
"""

import logging
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from caixa_nfse.core.services.sql_executor import SQLExecutor

logger = logging.getLogger(__name__)


class ImportadorMovimentos:
    """Orchestrates import of movements from external databases."""

    @staticmethod
    def executar_rotinas(conexao, rotinas, data_inicio, data_fim):
        """
        Execute multiple rotinas against an external connection.
        Returns list of (rotina, headers, rows, logs) tuples.
        """
        resultados = []
        for rotina in rotinas:
            sql = f"{rotina.sql_content}\n{rotina.sql_content_extra or ''}"
            params = {
                "DATA_INICIO": data_inicio,
                "DATA_FIM": data_fim,
            }
            headers, rows, logs = SQLExecutor.execute_routine(conexao, sql, params)
            resultados.append((rotina, headers, rows, logs))
        return resultados

    @staticmethod
    def mapear_colunas(rotina, headers, row):
        """
        Map a single result row to a dict of MovimentoImportado field values
        using the MapeamentoColunaRotina configuration.
        """
        mapeamentos = {m.coluna_sql.upper(): m.campo_destino for m in rotina.mapeamentos.all()}

        mapped = {}
        for i, header in enumerate(headers):
            campo = mapeamentos.get(header.upper())
            if campo and i < len(row):
                mapped[campo] = row[i]

        return mapped

    @staticmethod
    def _parse_decimal(value):
        """Safely parse a value to Decimal."""
        if value is None:
            return Decimal("0.00")
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(str(value).strip().replace(",", "."))
        except (InvalidOperation, ValueError):
            return Decimal("0.00")

    @staticmethod
    def salvar_importacao(abertura, conexao, rotina, headers, rows, user):
        """
        Map and save multiple rows as MovimentoImportado records.
        Returns count of created records.
        """
        from caixa_nfse.caixa.models import MovimentoImportado

        DECIMAL_FIELDS = set(MovimentoImportado.TAXA_FIELDS) | {"valor"}

        importados = []
        for row in rows:
            mapped = ImportadorMovimentos.mapear_colunas(rotina, headers, row)
            if not mapped:
                continue

            kwargs = {
                "tenant": user.tenant,
                "abertura": abertura,
                "conexao": conexao,
                "rotina": rotina,
                "importado_por": user,
            }

            for campo, valor in mapped.items():
                if campo in DECIMAL_FIELDS:
                    kwargs[campo] = ImportadorMovimentos._parse_decimal(valor)
                elif campo == "quantidade":
                    try:
                        kwargs[campo] = int(valor) if valor else 1
                    except (ValueError, TypeError):
                        kwargs[campo] = 1
                else:
                    kwargs[campo] = str(valor or "")[:500]

            importados.append(MovimentoImportado(**kwargs))

        created = MovimentoImportado.objects.bulk_create(importados)
        return len(created)

    @staticmethod
    @transaction.atomic
    def confirmar_movimentos(ids, abertura, forma_pagamento, tipo, user):
        """
        Migrate selected MovimentoImportado records to MovimentoCaixa.
        Returns count of confirmed movements.
        """
        from caixa_nfse.caixa.models import MovimentoCaixa, MovimentoImportado

        importados = MovimentoImportado.objects.filter(
            pk__in=ids,
            abertura=abertura,
            confirmado=False,
            tenant=user.tenant,
        )

        count = 0
        caixa = abertura.caixa

        for imp in importados:
            mov_kwargs = {
                "tenant": user.tenant,
                "abertura": abertura,
                "tipo": tipo,
                "forma_pagamento": forma_pagamento,
                "valor": imp.valor or imp.valor_total_taxas,
                "descricao": imp.descricao or f"Protocolo {imp.protocolo}",
                "created_by": user,
                "protocolo": imp.protocolo,
                "status_item": imp.status_item,
                "quantidade": imp.quantidade,
            }

            # Copy tax fields
            for field in MovimentoImportado.TAXA_FIELDS:
                mov_kwargs[field] = getattr(imp, field) or Decimal("0.00")

            movimento = MovimentoCaixa.objects.create(**mov_kwargs)

            # Update caixa balance
            if movimento.is_entrada:
                caixa.saldo_atual += movimento.valor
            else:
                caixa.saldo_atual -= movimento.valor

            # Mark as confirmed
            imp.confirmado = True
            imp.confirmado_em = timezone.now()
            imp.movimento_destino = movimento
            imp.save(update_fields=["confirmado", "confirmado_em", "movimento_destino"])
            count += 1

        caixa.save(update_fields=["saldo_atual"])
        return count

    @staticmethod
    def limpar_confirmados(tenant):
        """Delete all confirmed imported movements for a tenant."""
        from caixa_nfse.caixa.models import MovimentoImportado

        deleted, _ = MovimentoImportado.objects.filter(tenant=tenant, confirmado=True).delete()
        return deleted
