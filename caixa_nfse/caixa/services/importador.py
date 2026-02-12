"""
Service layer for importing movements from external databases via Rotinas SQL.
"""

import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from caixa_nfse.core.services.sql_executor import SQLExecutor

logger = logging.getLogger(__name__)


class ImportadorMovimentos:
    """Orchestrates import of movements from external databases."""

    @staticmethod
    def executar_rotinas(conexao, rotinas, params=None):
        """
        Execute multiple rotinas against an external connection.
        Accepts dynamic params dict (e.g. {"DATA_INICIO": "...", "PROTOCOLO": "..."}).
        Returns list of (rotina, headers, rows, logs) tuples.
        """
        if params is None:
            params = {}

        resultados = []
        for rotina in rotinas:
            sql_parts = [rotina.sql_content.strip()]
            if rotina.sql_content_extra:
                sql_parts.append(rotina.sql_content_extra.strip())
            sql = "\n".join(sql_parts).replace("\r", "")
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
        "VALORRECEITAADICIONAL1": "taxa_judiciaria",
        "VALORRECEITAADICIONAL2": "valor_receita_adicional_2",
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
        # data do ato
        "DATA_ATO": "data_ato",
        "DATAATO": "data_ato",
        "DATA_CONFECCAO": "data_ato",
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

    # Fields that should be accumulated (summed) when multiple columns map to the same target
    _ACCUMULATE_FIELDS = {
        "valor",
        "emolumento",
        "taxa_judiciaria",
        "iss",
        "fundesp",
        "funesp",
        "estado",
        "fesemps",
        "funemp",
        "funcomp",
        "fepadsaj",
        "funproge",
        "fundepeg",
        "fundaf",
        "femal",
        "fecad",
        "valor_receita_adicional_1",
        "valor_receita_adicional_2",
    }

    @staticmethod
    def mapear_colunas(rotina, headers, row):
        """
        Map a single result row to a dict of MovimentoImportado field values.
        Uses MapeamentoColunaRotina if configured, otherwise falls back to
        auto-mapping based on column name aliases.
        When multiple SQL columns map to the same decimal target (e.g. VALOR +
        VALORRECEITAADICIONAL1), values are accumulated (summed) instead of
        overwritten.
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
                # Accumulate decimal fields when same target appears multiple times
                if campo in ImportadorMovimentos._ACCUMULATE_FIELDS and campo in mapped:
                    existing = ImportadorMovimentos._parse_decimal(mapped[campo])
                    new_val = ImportadorMovimentos._parse_decimal(row[i])
                    mapped[campo] = str(existing + new_val)
                else:
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
    def _parse_date(value):
        """Parse a date value from SQL into a Python date object."""
        if value is None:
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, datetime):
            return value.date()
        s = str(value).strip()
        if not s:
            return None
        for fmt in ("%Y%m%d", "%d/%m/%Y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def salvar_importacao(abertura, conexao, rotina, headers, rows, user):
        """
        Map and save multiple rows as MovimentoImportado records.
        Also creates ItemAtoImportado children for each individual row.
        Returns tuple (created_count, skipped_count).
        Skips rows whose protocolo already exists for the same sistema+rotina.
        """
        from caixa_nfse.caixa.models import ItemAtoImportado, MovimentoImportado

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

        # Helper to normalize description
        def normalize_desc(d):
            return " ".join(str(d).split()) if d else ""

        grouped_data = {}
        skipped = 0

        # 1. First pass: Group rows by protocol
        for row in rows:
            mapped = ImportadorMovimentos.mapear_colunas(rotina, headers, row)
            if not mapped:
                continue

            protocolo = str(mapped.get("protocolo", "") or "").strip()

            # Check if protocol exists in DB
            if protocolo and protocolo in existing:
                skipped += 1
                continue

            # Key for grouping
            group_key = protocolo if protocolo else f"NO_PROTO_{len(grouped_data)}"

            if group_key not in grouped_data:
                grouped_data[group_key] = {
                    "protocolo": protocolo,
                    "valor": Decimal("0.00"),
                    "taxas": {f: Decimal("0.00") for f in DECIMAL_FIELDS if f != "valor"},
                    "descricoes": [],
                    "first_mapped": mapped,
                    "raw_items": [],  # Store each row for child creation
                }

            # Accumulate values
            group = grouped_data[group_key]

            # Valor principal
            valor_row = ImportadorMovimentos._parse_decimal(mapped.get("valor"))
            group["valor"] += valor_row

            # Taxas
            for tax_field in group["taxas"]:
                val_tax = ImportadorMovimentos._parse_decimal(mapped.get(tax_field))
                group["taxas"][tax_field] += val_tax

            # Collect description (avoid duplicates)
            desc = normalize_desc(mapped.get("descricao"))
            if desc and desc not in group["descricoes"]:
                group["descricoes"].append(desc)

            # Store raw mapped row for children
            group["raw_items"].append(mapped)

        # 2. Second pass: Create parent objects
        importados = []
        importados_raw = []  # parallel list of raw_items for each parent
        for _, data in grouped_data.items():
            first = data["first_mapped"]
            protocolo = data["protocolo"]

            # Format description
            desc_list = data["descricoes"]
            if desc_list:
                combined_desc = "; ".join(desc_list)
                final_descricao = f"{rotina.nome} - {combined_desc}"
            else:
                final_descricao = f"{rotina.nome}"
            final_descricao = final_descricao[:500]

            kwargs = {
                "tenant": user.tenant,
                "abertura": abertura,
                "conexao": conexao,
                "rotina": rotina,
                "importado_por": user,
                "protocolo": protocolo,
                "valor": data["valor"],
                "descricao": final_descricao,
            }

            # Populate tax fields
            for tax_field, tax_val in data["taxas"].items():
                kwargs[tax_field] = tax_val

            # Populate non-summable fields from first record
            kwargs["cliente_nome"] = str(first.get("cliente_nome") or "")[:200]
            kwargs["status_item"] = str(first.get("status_item") or "")[:100]

            q_val = first.get("quantidade")
            try:
                kwargs["quantidade"] = int(q_val) if q_val else 1
            except (ValueError, TypeError):
                kwargs["quantidade"] = 1

            data_ato = ImportadorMovimentos._parse_date(first.get("data_ato"))
            if data_ato:
                kwargs["data_ato"] = data_ato

            importados.append(MovimentoImportado(**kwargs))
            importados_raw.append(data["raw_items"])
            if protocolo:
                existing.add(protocolo)

        created = MovimentoImportado.objects.bulk_create(importados)

        # 3. Third pass: Create child ItemAtoImportado records
        child_items = []
        for parent, raw_items in zip(created, importados_raw, strict=True):
            for mapped in raw_items:
                item_kwargs = {
                    "tenant": user.tenant,
                    "movimento_importado": parent,
                    "descricao": normalize_desc(mapped.get("descricao"))[:500],
                    "valor": ImportadorMovimentos._parse_decimal(mapped.get("valor")),
                    "cliente_nome": str(mapped.get("cliente_nome") or "")[:200],
                    "status_item": str(mapped.get("status_item") or "")[:100],
                }
                # Quantity
                q = mapped.get("quantidade")
                try:
                    item_kwargs["quantidade"] = int(q) if q else 1
                except (ValueError, TypeError):
                    item_kwargs["quantidade"] = 1
                # Date
                d = ImportadorMovimentos._parse_date(mapped.get("data_ato"))
                if d:
                    item_kwargs["data_ato"] = d
                # Tax fields
                for tf in MovimentoImportado.TAXA_FIELDS:
                    item_kwargs[tf] = ImportadorMovimentos._parse_decimal(mapped.get(tf))

                child_items.append(ItemAtoImportado(**item_kwargs))

        if child_items:
            ItemAtoImportado.objects.bulk_create(child_items)

        return len(created), skipped

    @staticmethod
    @transaction.atomic
    def confirmar_movimentos(ids, abertura, forma_pagamento, tipo, user, parcelas_map=None):
        """
        Migrate selected MovimentoImportado records to MovimentoCaixa.
        Supports partial payments via parcelas_map: {importado_id: valor_parcela}.
        If parcelas_map is None, pays the full remaining balance.
        Also copies ItemAtoImportado children to ItemAtoMovimento.
        Auto-registers Cliente from apresentante name if available.
        Returns count of confirmed movements.
        """
        from caixa_nfse.caixa.models import (
            ItemAtoMovimento,
            MovimentoCaixa,
            MovimentoImportado,
            ParcelaRecebimento,
            StatusRecebimento,
        )
        from caixa_nfse.clientes.models import Cliente

        if parcelas_map is None:
            parcelas_map = {}

        # Fields to copy from ItemAtoImportado to ItemAtoMovimento
        item_copy_fields = [
            "descricao",
            "valor",
            "quantidade",
            "data_ato",
            "status_item",
            "cliente_nome",
        ] + MovimentoCaixa.TAXA_FIELDS

        importados = (
            MovimentoImportado.objects.prefetch_related("itens", "parcelas")
            .filter(
                pk__in=ids,
                abertura=abertura,
                tenant=user.tenant,
            )
            .exclude(status_recebimento=StatusRecebimento.QUITADO)
        )

        count = 0
        caixa = abertura.caixa
        movimentos_para_nfse = []

        for imp in importados:
            # Determine payment value
            str_id = str(imp.pk)
            if str_id in parcelas_map:
                valor_parcela = Decimal(str(parcelas_map[str_id]))
            elif imp.pk in parcelas_map:
                valor_parcela = Decimal(str(parcelas_map[imp.pk]))
            else:
                valor_parcela = imp.saldo_pendente

            # Validate
            saldo = imp.saldo_pendente
            if valor_parcela <= Decimal("0.00"):
                continue
            if valor_parcela > saldo:
                valor_parcela = saldo

            # Determine if this is full payment
            is_quitacao = valor_parcela >= saldo
            numero_parcela = imp.parcelas.count() + 1

            # Auto-register client from apresentante name (only on first parcela)
            cliente = None
            if imp.cliente_nome and numero_parcela == 1:
                cliente = Cliente.objects.create(
                    tenant=user.tenant,
                    razao_social=imp.cliente_nome.strip(),
                    cadastro_completo=False,
                )

            # Build description
            parts = []
            if imp.descricao:
                parts.append(imp.descricao)
            if not parts:
                parts.append(f"Protocolo {imp.protocolo}")
            if not is_quitacao:
                parts.append(f"Parcela {numero_parcela}")
            descricao = " — ".join(parts)

            mov_kwargs = {
                "tenant": user.tenant,
                "abertura": abertura,
                "tipo": tipo,
                "forma_pagamento": forma_pagamento,
                "valor": valor_parcela,
                "descricao": descricao,
                "created_by": user,
                "protocolo": imp.protocolo,
                "status_item": imp.status_item,
                "quantidade": imp.quantidade,
                "cliente": cliente,
                "data_ato": imp.data_ato,
            }

            # Copy tax fields only on the first parcela
            for field in MovimentoImportado.TAXA_FIELDS:
                if numero_parcela == 1:
                    mov_kwargs[field] = getattr(imp, field) or Decimal("0.00")
                else:
                    mov_kwargs[field] = Decimal("0.00")

            movimento = MovimentoCaixa.objects.create(**mov_kwargs)

            # Copy child items: ItemAtoImportado → ItemAtoMovimento (only on first parcela)
            if numero_parcela == 1:
                child_items = []
                for item in imp.itens.all():
                    item_data = {"tenant": user.tenant, "movimento": movimento}
                    for f in item_copy_fields:
                        val = getattr(item, f, None)
                        if val is None or val == "":
                            if f in MovimentoImportado.TAXA_FIELDS or f == "valor":
                                val = Decimal("0.00")
                            elif f in ("data_ato",):
                                val = None
                            elif f == "quantidade":
                                val = 1
                            else:
                                val = ""
                        item_data[f] = val
                    child_items.append(ItemAtoMovimento(**item_data))
                if child_items:
                    ItemAtoMovimento.objects.bulk_create(child_items)

            # Create ParcelaRecebimento
            ParcelaRecebimento.objects.create(
                tenant=user.tenant,
                movimento_importado=imp,
                movimento_caixa=movimento,
                abertura=abertura,
                forma_pagamento=forma_pagamento,
                valor=valor_parcela,
                numero_parcela=numero_parcela,
                recebido_por=user,
            )

            # Update caixa balance
            if movimento.is_entrada:
                caixa.saldo_atual += movimento.valor
            else:
                caixa.saldo_atual -= movimento.valor

            # Update MovimentoImportado status
            if is_quitacao:
                imp.confirmado = True
                imp.confirmado_em = timezone.now()
                imp.movimento_destino = movimento
                imp.status_recebimento = StatusRecebimento.QUITADO
                imp.save(
                    update_fields=[
                        "confirmado",
                        "confirmado_em",
                        "movimento_destino",
                        "status_recebimento",
                    ]
                )
            else:
                imp.status_recebimento = StatusRecebimento.PARCIAL
                imp.save(update_fields=["status_recebimento"])

            count += 1

            # Collect for NFS-e dispatch (only on quitação)
            if is_quitacao and cliente:
                movimentos_para_nfse.append(str(movimento.pk))

        caixa.save(update_fields=["saldo_atual"])

        # Dispatch NFS-e tasks after transaction commits (only for quitação)
        if movimentos_para_nfse and _deve_gerar_nfse(user.tenant):
            from caixa_nfse.nfse.tasks import emitir_nfse_movimento

            for mov_id in movimentos_para_nfse:
                transaction.on_commit(lambda mid=mov_id: emitir_nfse_movimento.delay(mid))

        return count

    @staticmethod
    def limpar_confirmados(tenant):
        """Delete all confirmed imported movements for a tenant."""
        from caixa_nfse.caixa.models import MovimentoImportado

        deleted, _ = MovimentoImportado.objects.filter(tenant=tenant, confirmado=True).delete()
        return deleted

    @staticmethod
    def migrar_pendentes_para_nova_abertura(nova_abertura):
        """
        Re-link PENDENTE/PARCIAL imports from closed sessions to the new opening.
        Cross-caixa: pendentes belong to the tenant, appear on any register.
        """
        from caixa_nfse.caixa.models import MovimentoImportado, StatusRecebimento

        pendentes = MovimentoImportado.objects.filter(
            tenant=nova_abertura.tenant,
            abertura__fechamento__isnull=False,  # abertura was closed
            status_recebimento__in=[
                StatusRecebimento.PENDENTE,
                StatusRecebimento.PARCIAL,
                StatusRecebimento.VENCIDO,
            ],
        )
        count = pendentes.update(abertura=nova_abertura)
        return count


def _deve_gerar_nfse(tenant):
    """Verifica se o tenant possui geração automática de NFS-e ativa."""
    from caixa_nfse.nfse.models import ConfiguracaoNFSe

    config = ConfiguracaoNFSe.objects.filter(tenant=tenant).first()
    if config is None:
        return False
    return config.gerar_nfse_ao_confirmar
