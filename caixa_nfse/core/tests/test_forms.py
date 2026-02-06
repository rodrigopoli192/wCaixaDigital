import pytest

from caixa_nfse.core.forms import FormaPagamentoForm
from caixa_nfse.tests.factories import FormaPagamentoFactory, TenantFactory


@pytest.mark.django_db
class TestFormaPagamentoForm:
    """Tests for FormaPagamentoForm."""

    def test_valid_form(self):
        """Should be valid with correct data."""
        data = {
            "nome": "Dinheiro",
            "tipo": "DINHEIRO",
            "taxa_percentual": "0.00",
            "prazo_recebimento": "0",
            "ativo": True,
        }
        form = FormaPagamentoForm(data=data)
        assert form.is_valid()

    def test_default_ativo(self):
        """Should set ativo=True for new records if not provided."""
        form = FormaPagamentoForm()
        assert form.fields["ativo"].initial is True

    def test_invalid_taxa(self):
        """Should validate weak typing or constraints if any (model has none strict?)"""
        # Model fields usually handle validation. Form just passes data.
        # Let's check required fields.
        form = FormaPagamentoForm(data={})
        assert not form.is_valid()
        assert "nome" in form.errors
        assert "tipo" in form.errors

    def test_init_with_instance(self):
        """Should NOT force ativo=True on existing instance."""
        # Need a saved instance (requires DB access, so use factory)
        t = TenantFactory()
        # FormaPagamentoFactory has tenant, nome, codigo, ativo.
        fp = FormaPagamentoFactory(nome="Old", ativo=False, tenant=t)

        form = FormaPagamentoForm(instance=fp)
        # initial shouldn't be overridden if instance has PK
        # form.fields['ativo'].initial is what we check in code?
        # Code: if not self.instance.pk: self.fields["ativo"].initial = True
        # So if instance.pk, initial is NOT set to True.

        # Django ModelForm uses instance values for initial, but does it set field.initial attribute?
        # Usually checking the rendered html or bound data is better, but checking the attribute logic:
        # When instance is provided, form should respect instance value
        assert form.initial["ativo"] is False
