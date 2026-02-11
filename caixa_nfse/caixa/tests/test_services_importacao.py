from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase

from caixa_nfse.caixa.services.importador import ImportadorMovimentos


class TestImportadorMovimentos(TestCase):
    def test_salvar_importacao_grouping(self):
        # Setup mocks
        abertura = MagicMock()
        conexao = MagicMock()
        conexao.sistema = "SISTEMA_TESTE"
        rotina = MagicMock()
        rotina.nome = "Rotina X"
        user = MagicMock()
        user.tenant = MagicMock()

        headers = ["PROTOCOLO", "VALOR", "ISS", "DESCRICAO", "CLIENTE_NOME"]

        # 3 rows with same protocol
        rows = [
            ("12345", "100.00", "10.00", "Desc 1", "Cliente A"),
            ("12345", "50.00", "5.00", "Desc 2", "Cliente B"),
            ("12345", "200.00", "20.00", "Desc 1", "Cliente A"),
        ]

        with (
            patch("caixa_nfse.caixa.models.MovimentoImportado") as MockMI,
            patch("caixa_nfse.caixa.models.ItemAtoImportado") as MockIAI,
        ):
            # bulk_create for parent must return a list matching len(importados)
            parent_obj = MagicMock()
            MockMI.objects.bulk_create.return_value = [parent_obj]
            MockMI.TAXA_FIELDS = ["iss"]

            def mi_side_effect(**kwargs):
                m = MagicMock()
                for k, v in kwargs.items():
                    setattr(m, k, v)
                return m

            MockMI.side_effect = mi_side_effect

            # ItemAtoImportado mock
            MockIAI.side_effect = mi_side_effect
            MockIAI.objects.bulk_create.return_value = []

            count, skipped = ImportadorMovimentos.salvar_importacao(
                abertura, conexao, rotina, headers, rows, user
            )

            self.assertEqual(count, 1)
            self.assertEqual(skipped, 0)

            args, _ = MockMI.objects.bulk_create.call_args
            created_list = args[0]
            self.assertEqual(len(created_list), 1)

            mov = created_list[0]
            self.assertEqual(mov.valor, Decimal("350.00"))
            self.assertEqual(mov.iss, Decimal("35.00"))

            expected_desc = "Rotina X - Desc 1; Desc 2"
            self.assertEqual(mov.descricao, expected_desc)

            self.assertEqual(mov.cliente_nome, "Cliente A")
            self.assertEqual(mov.protocolo, "12345")

            # Verify ItemAtoImportado children were created (3 items)
            child_args, _ = MockIAI.objects.bulk_create.call_args
            child_list = child_args[0]
            self.assertEqual(len(child_list), 3)
