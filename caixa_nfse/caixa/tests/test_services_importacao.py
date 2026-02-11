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

        # Mock MapeamentoColunaRotina (or just rely on automap if headers match aliases)
        # We will use auto-mapping for simplicity
        headers = ["PROTOCOLO", "VALOR", "ISS", "DESCRICAO", "CLIENTE_NOME"]

        # 3 rows with same protocol
        rows = [
            # Row 1: Valor 100, ISS 10, Desc "Desc 1", Cliente "Cliente A"
            ("12345", "100.00", "10.00", "Desc 1", "Cliente A"),
            # Row 2: Valor 50, ISS 5, Desc "Desc 2", Cliente "Cliente B" (should use A)
            ("12345", "50.00", "5.00", "Desc 2", "Cliente B"),
            # Row 3: Valor 200, ISS 20, Desc "Desc 1", Cliente "Cliente A" (duplicate desc)
            ("12345", "200.00", "20.00", "Desc 1", "Cliente A"),
        ]

        # Mock MovimentoImportado class (not just objects)
        with patch("caixa_nfse.caixa.models.MovimentoImportado") as MockMovimentoImportado:
            MockMovimentoImportado.objects.bulk_create.return_value = [1]  # Dummy return
            MockMovimentoImportado.TAXA_FIELDS = ["iss"]  # Only need ISS for test

            # Setup constructor to return an object (so append works)
            def side_effect(**kwargs):
                m = MagicMock()
                for k, v in kwargs.items():
                    setattr(m, k, v)
                return m

            MockMovimentoImportado.side_effect = side_effect

            # Execute
            count, skipped = ImportadorMovimentos.salvar_importacao(
                abertura, conexao, rotina, headers, rows, user
            )

            # Assertions
            self.assertEqual(count, 1)  # Grouped into 1
            self.assertEqual(skipped, 0)

            # Verify bulk_create called with our mock instance
            args, _ = MockMovimentoImportado.objects.bulk_create.call_args
            created_list = args[0]
            self.assertEqual(len(created_list), 1)

            mov = created_list[0]

            # Sum logic
            self.assertEqual(mov.valor, Decimal("350.00"))  # 100+50+200
            self.assertEqual(mov.iss, Decimal("35.00"))  # 10+5+20

            # Description logic: name + unique descs
            # Expected: "Rotina X - Desc 1; Desc 2"
            expected_desc = "Rotina X - Desc 1; Desc 2"
            self.assertEqual(mov.descricao, expected_desc)

            # First wins logic
            self.assertEqual(mov.cliente_nome, "Cliente A")
            self.assertEqual(mov.protocolo, "12345")
