"""
Tests for validar_cpf and validar_cnpj functions.
"""

from caixa_nfse.clientes.models import validar_cnpj, validar_cpf


class TestValidarCPF:
    """Tests for validar_cpf."""

    def test_valid_cpf(self):
        assert validar_cpf("529.982.247-25") is True

    def test_valid_cpf_unmasked(self):
        assert validar_cpf("52998224725") is True

    def test_all_same_digits(self):
        assert validar_cpf("11111111111") is False

    def test_all_zeros(self):
        assert validar_cpf("00000000000") is False

    def test_wrong_length(self):
        assert validar_cpf("1234567") is False

    def test_invalid_checksum(self):
        assert validar_cpf("12345678900") is False

    def test_empty_string(self):
        assert validar_cpf("") is False

    def test_with_mask_invalid(self):
        assert validar_cpf("111.111.111-11") is False


class TestValidarCNPJ:
    """Tests for validar_cnpj."""

    def test_valid_cnpj(self):
        assert validar_cnpj("11.222.333/0001-81") is True

    def test_valid_cnpj_unmasked(self):
        assert validar_cnpj("11222333000181") is True

    def test_all_same_digits(self):
        assert validar_cnpj("11111111111111") is False

    def test_all_zeros(self):
        assert validar_cnpj("00000000000000") is False

    def test_wrong_length(self):
        assert validar_cnpj("123456") is False

    def test_invalid_checksum(self):
        assert validar_cnpj("12345678000100") is False

    def test_empty_string(self):
        assert validar_cnpj("") is False

    def test_with_mask_invalid(self):
        assert validar_cnpj("11.111.111/1111-11") is False

    def test_valid_second_digit(self):
        """Exercícia o segundo dígito verificador."""
        assert validar_cnpj("11222333000181") is True
        # Alterar último dígito invalida
        assert validar_cnpj("11222333000182") is False
