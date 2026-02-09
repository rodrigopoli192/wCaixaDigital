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
            sql_parts = [rotina.sql_content.strip()]
            if rotina.sql_content_extra:
                sql_parts.append(rotina.sql_content_extra.strip())
            sql = "\n".join(sql_parts).replace("\r", "")
            params = {
                "DATA_INICIO": data_inicio,
                "DATA_FIM": data_fim,
            }
            headers, rows, logs = SQLExecutor.execute_routine(conexao, sql, params)
            resultados.append((rotina, headers, rows, logs))
        return resultados

    # Auto-mapping aliases: SQL column names -> campo_destino
    AUTO_MAP_ALIASES = {
        # protocolo
        "PROTOCOLO": "protocolo",
        "NR_PROTOCOLO": "protocolo",
        "CHAVE_PED_CERTIDOES": "protocolo",
        "CHAVE_PEDIDO_REGISTRO": "protocolo",
        "NUMERO_PROTOCOLO": "protocolo",
        # descricao
        "DESCRICAO": "descricao",
        "DESCRICAO_ATO": "descricao",
        "NOME_ATO": "descricao",
        "TIPO": "descricao",
        # cliente_nome
        "CLIENTE_NOME": "cliente_nome",
        "NOMEAPRESENTANTE": "cliente_nome",
        "NOME_APRESENTANTE": "cliente_nome",
        "SOLICITANTE": "cliente_nome",
        "NOME_SOLICITANTE": "cliente_nome",
        "APRESENTANTE": "cliente_nome",
        # valor
        "VALOR": "valor",
        "VALOR_PRINCIPAL": "valor",
        "VALOREMOLUMENTO": "emolumento",
        # emolumento
        "EMOLUMENTO": "emolumento",
        "VALOR_EMOLUMENTO": "emolumento",
        # quantidade
        "QTD": "quantidade",
        "QUANTIDADE": "quantidade",
        # status
        "STATUS": "status_item",
        "STATUS_PAGAMENTO": "status_item",
        "DATA_PAGAMENTO": "status_item",
        # taxa_judiciaria
        "TAXA_JUDICIARIA": "taxa_judiciaria",
        "TX_JUDICIARIA": "taxa_judiciaria",
        # taxas numeradas (TAXA1..TAXA15 -> campos de taxa)
        "TAXA1": "iss",
        "TAXA2": "fundesp",
        "TAXA3": "funesp",
        "TAXA4": "estado",
        "TAXA5": "fesemps",
        "TAXA6": "funemp",
        "TAXA7": "funcomp",
        "TAXA8": "fepadsaj",
        "TAXA9": "funproge",
        "TAXA10": "fundepeg",
        "TAXA11": "fundaf",
        "TAXA12": "femal",
        "TAXA13": "fecad",
        # direct matches
        "ISS": "iss",
        "FUNDESP": "fundesp",
        "FUNESP": "funesp",
        "ESTADO": "estado",
        "FESEMPS": "fesemps",
        "FUNEMP": "funemp",
        "FUNCOMP": "funcomp",
        "FEPADSAJ": "fepadsaj",
        "FUNPROGE": "funproge",
        "FUNDEPEG": "fundepeg",
        "FUNDAF": "fundaf",
        "FEMAL": "femal",
        "FECAD": "fecad",
    }

    @staticmethod
    def mapear_colunas(rotina, headers, row):
        """
        Map a single result row to a dict of MovimentoImportado field values.
        Uses MapeamentoColunaRotina if configured, otherwise falls back to
        auto-mapping based on column name aliases.
        """
        manual = {m.coluna_sql.upper(): m.campo_destino for m in rotina.mapeamentos.all()}
        use_auto = not manual

        mapped = {}
        for i, header in enumerate(headers):
            h = header.upper()
            if use_auto:
                campo = ImportadorMovimentos.AUTO_MAP_ALIASES.get(h)
            else:
                campo = manual.get(h)
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
        Returns tuple (created_count, skipped_count).
        Skips rows whose protocolo already exists for the same sistema+rotina.
        """
        from caixa_nfse.caixa.models import MovimentoImportado

        DECIMAL_FIELDS = set(MovimentoImportado.TAXA_FIELDS) | {"valor"}

        # Fetch existing protocolos for this sistema + rotina
        existing = set(
            MovimentoImportado.objects.filter(
                tenant=user.tenant,
                conexao__sistema=conexao.sistema,
                rotina=rotina,
            )
            .exclude(protocolo="")
            .values_list("protocolo", flat=True)
        )

        importados = []
        skipped = 0
        for row in rows:
            mapped = ImportadorMovimentos.mapear_colunas(rotina, headers, row)
            if not mapped:
                continue

            protocolo = str(mapped.get("protocolo", "") or "").strip()
            if protocolo and protocolo in existing:
                skipped += 1
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
            if protocolo:
                existing.add(protocolo)

        created = MovimentoImportado.objects.bulk_create(importados)
        return len(created), skipped

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
